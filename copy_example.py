Import("env")

# Do nothing when PlatformIO is:
#   - gathering IDE integration information
#   - performing a clean operation
if env.IsIntegrationDump() or env.IsCleanTarget():
    Return()


from pathlib import Path


project_dir = Path(env["PROJECT_DIR"])
tmp_path = project_dir / "src" / "__tmp.ino"


def remove_tmp():
    """Remove the generated tmp.ino file."""
    if tmp_path.exists():
        tmp_path.unlink()
        print(f"Removed {tmp_path}")


def create_tmp():
    # Remove anything left over from a previous build.
    remove_tmp()  

    example_ino = env.GetProjectOption("custom_example_ino")

    if not example_ino:
        raise RuntimeError("custom_example_ino is not defined in platformio.ini")

    example_path = project_dir / example_ino

    if not example_path.is_file():
        raise FileNotFoundError(
            f"example_ino does not exist: {example_path}"
        )
    

    # Path from src/ to the example .ino.
    include_path = Path("..") / example_path.relative_to(project_dir)

    tmp_path.write_text(
        f'#include "{include_path.as_posix()}"\n',
        encoding="utf-8"
    )
    tmp_path.write_text(
        f"""// This temporary file was automatically generated as a workaround to compile ino files from the examples folder without having to move them into the src folder.
#include "{include_path.as_posix()}"
        """,
        encoding="utf-8"
    )

    print(f"Generated {tmp_path}")


create_tmp()
# Remove __tmp.ino after the build completes.
env.AddPostAction("$BUILD_DIR/${PROGNAME}.elf", lambda source, target, env: remove_tmp())

