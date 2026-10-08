from pathlib import Path
import shutil


ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"pv_forecast_calibrator"
TARGET=ROOT/"pv-forecast-calibrator"/"rootfs"/"usr"/"src"/"app"/"pv_forecast_calibrator"


def sync_package():
	if not TARGET.resolve().is_relative_to(ROOT.resolve()):
		raise RuntimeError(f"Generated target escapes repository: {TARGET}")
	TARGET.mkdir(parents=True,exist_ok=True)
	expected=set()
	for source in SOURCE.rglob("*"):
		if not source.is_file() or "__pycache__" in source.parts:
			continue
		relative=source.relative_to(SOURCE)
		expected.add(relative)
		destination=TARGET/relative
		destination.parent.mkdir(parents=True,exist_ok=True)
		shutil.copy2(source,destination)
	for generated in sorted(TARGET.rglob("*"),reverse=True):
		if generated.is_file() and generated.relative_to(TARGET) not in expected:
			generated.unlink()
		elif generated.is_dir() and not any(generated.iterdir()):
			generated.rmdir()


if __name__ == "__main__":
	sync_package()
