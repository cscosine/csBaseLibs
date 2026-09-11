import json
import shutil
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from .package_version import (
    CMakeConfigPackageVersionGrep,
    PackageVersion,
    get_package_versions_helper,
)


@dataclass
class ManifestVersionsEntry:
    variant: str
    entries: list[PackageVersion] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ManifestVersionsEntry":
        return cls(
            variant=data["variant"],
            entries=[PackageVersion.from_dict(entry) for entry in data["entries"]],
        )


@dataclass
class ReleaseManifest:
    project_name: str
    project_version: str
    additional_files: list[str]
    output_bundle_file_name: str | None
    variants: list[ManifestVersionsEntry] = field(default_factory=list)

    MANIFEST_VERSION: ClassVar[str] = "1.0"
    manifest_version: str = MANIFEST_VERSION

    CS_ORCHESTRATOR_MANIFEST_EXTENSION: ClassVar[str] = ".csOrchestratorManifest"
    CS_ORCHESTRATOR_MANIFEST_ROOT: ClassVar[str] = "csOrchestratorManifest"

    def to_dict(self) -> dict[str, Any]:
        return {
            ReleaseManifest.CS_ORCHESTRATOR_MANIFEST_ROOT: {
                "manifest_version": self.manifest_version,
                "project_name": self.project_name,
                "project_version": self.project_version,
                "variants": [variant.to_dict() for variant in self.variants],
                "additional_files": list(self.additional_files),
                "output_bundle_file_name": self.output_bundle_file_name,
            }
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReleaseManifest":
        in_data = data[ReleaseManifest.CS_ORCHESTRATOR_MANIFEST_ROOT]
        return cls(
            manifest_version=in_data["manifest_version"],
            project_name=in_data["project_name"],
            project_version=in_data["project_version"],
            variants=[ManifestVersionsEntry.from_dict(variant) for variant in in_data["variants"]],
            additional_files=in_data["additional_files"],
            output_bundle_file_name=in_data["output_bundle_file_name"],
        )

    def write_release_manifest(
        self,
        filename: Path,
    ) -> None:
        """Write a release manifest to a JSON file."""
        path = Path(filename)
        # TODO robustify and return possible errors
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)

    @classmethod
    def load_release_manifest(
        cls,
        filename: Path,
    ) -> "ReleaseManifest":
        """Load a release manifest from a JSON file."""
        path = Path(filename)
        # TODO robustify and return possible errors
        with path.open("r", encoding="utf-8") as f:
            return ReleaseManifest.from_dict(json.load(f))


def get_package_versions_and_write_single_variant_manifest(
    repos_config_file_list: list[CMakeConfigPackageVersionGrep],  # pairs of repo and files reporting versions
    repos_auto_search_list: list[str],  # repo name only
    repos_version: list[PackageVersion],  # pairs of repo and versions
    base_install_dir: Path,
    install_subdir: Path,
    variant_string: str,
    project_name: str,
    project_version: str,
    output_file: Path,
) -> list[str]:  # return errors

    result = get_package_versions_helper(
        repos_config_file_list,
        repos_auto_search_list,
        repos_version,
        base_install_dir,
        install_subdir,
    )

    if result.errors:
        return result.errors

    entry = ManifestVersionsEntry(variant=variant_string, entries=result.versions)
    manifest = ReleaseManifest(
        project_name=project_name,
        project_version=project_version,
        variants=[entry],
        additional_files=[],
        output_bundle_file_name=None,
    )

    manifest.write_release_manifest(output_file)

    return []


def load_release_manifest_single_variant(
    input_full_path: Path, expected_context_os_architecture_compiler_generator_string: str
) -> list[PackageVersion] | str:  # str in case of error
    packages = ReleaseManifest.load_release_manifest(input_full_path)
    if len(packages.variants) == 0 or len(packages.variants) > 1:
        return f"release manifest {str(input_full_path)} has {len(packages.variants)} variants, expected 1"

    if expected_context_os_architecture_compiler_generator_string != packages.variants[0].variant:
        return f"release manifest {str(input_full_path)} has variant name {packages.variants[0].variant}, expected {expected_context_os_architecture_compiler_generator_string}"  # noqa: E501

    return packages.variants[0].entries


def create_archive_filename(
    project_name_and_version: str,
    context_os_architecture_compiler_generator_string: str,
    lib_name: str,
    lib_version: str,
) -> str:
    return (
        project_name_and_version
        + "-"
        + lib_name
        + "-"
        + lib_version
        + "-"
        + context_os_architecture_compiler_generator_string
        + ".tar.gz"
    )


def load_release_manifest_single_variant_and_prepare_archive(
    input_full_path: Path,
    project_name_and_version: str,
    context_os_architecture_compiler_generator_string: str,
    input_base_dir: Path,
) -> list[str]:  # return errors
    # load which packages to create archives for from the version file (eg. eigen3: 3.4.0, boost: 1.82.0, etc)
    packages_or_error = load_release_manifest_single_variant(
        input_full_path, context_os_architecture_compiler_generator_string
    )

    if isinstance(packages_or_error, str):
        return [packages_or_error]
    packages = packages_or_error

    for item in packages:
        input_path = Path(
            input_base_dir / context_os_architecture_compiler_generator_string / Path(item.name)
        ).resolve()
        output_path = Path(
            input_base_dir
            / Path(
                create_archive_filename(
                    project_name_and_version, context_os_architecture_compiler_generator_string, item.name, item.version
                )
            )
        ).resolve()

        with tarfile.open(output_path, "w:gz") as tar:
            for path in input_path.rglob("*"):
                resolved_path = path.resolve()
                # make the archive self-contained: entries start directly with the
                # lib folder (e.g. "libassert/include/..."), not with the variant
                # folder, so that extracting into workspace/libs/<variant> makes the
                # package findable via CMAKE_PREFIX_PATH=<workspace>/libs/<variant>
                arcname = path.resolve().relative_to(input_path.parent)
                tar.add(resolved_path, arcname=arcname)

    return []


# TODO: manage errors
def copy_additional_files(
    base_path_additional_files: Path,
    list_additional_files: list[Path],
    output_folder_additional_files: Path,
) -> None:
    for file_path in list_additional_files:
        # Make the path absolute relative to the base path
        file_path = base_path_additional_files / file_path

        # Get the path relative to the base directory
        relative_path = file_path.relative_to(base_path_additional_files)

        # Preserve the subfolder structure in the output directory
        destination = output_folder_additional_files / relative_path

        # Create parent directories if needed
        destination.parent.mkdir(parents=True, exist_ok=True)

        # Copy the file
        shutil.copy2(file_path, destination)


def create_archive_additional_files(source_folder: Path, source_list: list[Path], output_archive: Path) -> None:
    # TODO manage errors
    with tarfile.open(output_archive, "w:gz") as tar:
        for path in source_list:
            resolved_path = (source_folder / path).resolve()
            arcname = (source_folder / path).resolve().relative_to(source_folder.resolve())
            tar.add(resolved_path, arcname=arcname)


def collect_release_manifest_single_variant_and_prepare_manifest(
    input_manifest_path_variant: list[tuple[Path, str]],
    output_filepath: Path,
    project_name: str,
    project_version: str,
    base_path_additional_files: Path,
    list_additional_files: list[Path],
    output_folder_additional_files: Path,
    output_bundle_file_name: Path,
) -> list[str]:  # return errors
    collected_version_entries: list[ManifestVersionsEntry] = []
    for input_full_path, context_os_architecture_compiler_generator_string in input_manifest_path_variant:
        packages_or_error = load_release_manifest_single_variant(
            input_full_path, context_os_architecture_compiler_generator_string
        )

        if isinstance(packages_or_error, str):
            return [packages_or_error]
        packages = packages_or_error

        collected_version_entries.append(
            ManifestVersionsEntry(variant=context_os_architecture_compiler_generator_string, entries=packages)
        )

    release_manifest = ReleaseManifest(
        project_name=project_name,
        project_version=project_version,
        variants=collected_version_entries,
        additional_files=[file.as_posix() for file in list_additional_files],
        output_bundle_file_name=output_bundle_file_name.as_posix(),
    )
    release_manifest.write_release_manifest(
        output_filepath,
    )

    if len(list_additional_files) > 0:
        copy_additional_files(
            base_path_additional_files=base_path_additional_files,
            list_additional_files=list_additional_files,
            output_folder_additional_files=output_folder_additional_files,
        )

        create_archive_additional_files(
            source_folder=output_folder_additional_files,
            source_list=list_additional_files,
            output_archive=output_folder_additional_files / output_bundle_file_name,
        )

    return []
