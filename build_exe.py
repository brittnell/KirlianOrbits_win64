import subprocess
import sys
import os
import shutil

def build():
    print("==================================================")
    print("      KIRLIAN ORBITS - WINDOWS COMPILER           ")
    print("==================================================")
    print("Preparing build environment...")
    
    project_dir = os.path.dirname(os.path.abspath(__file__))
    main_file = os.path.join(project_dir, "main.py")
    
    if not os.path.exists(main_file):
        print(f"Error: main.py not found at {main_file}")
        sys.exit(1)
        
    print(f"Project directory: {project_dir}")
    print("Running PyInstaller to compile Kirlian Orbits...")
    
    # Build PyInstaller command
    cmd = [
        "pyinstaller",
        "--onefile",
        "--noconsole",
        "--name=KirlianOrbits",
        "--icon=icon.ico",
        "--add-data=icon.png;.",
        "--hidden-import=mido.backends.rtmidi",
        "--hidden-import=rtmidi",
        "--clean",
        main_file
    ]
    
    try:
        # Run PyInstaller
        result = subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True, check=True)
        print(result.stdout)
        print("==================================================")
        print("SUCCESS: Standalone Kirlian Orbits compiled successfully!")
        
        exe_path = os.path.join(project_dir, "dist", "KirlianOrbits.exe")
        print(f"Executable location: {exe_path}")
        
        # Clean up temporary build artifacts
        print("Cleaning up temporary build artifacts...")
        build_dir = os.path.join(project_dir, "build")
        spec_file = os.path.join(project_dir, "KirlianOrbits.spec")
        
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
        if os.path.exists(spec_file):
            os.remove(spec_file)
            
        print("Clean up finished. Pristine workspaces maintained!")
        print("==================================================")
        
    except subprocess.CalledProcessError as e:
        print("==================================================")
        print("ERROR: Compilation failed during PyInstaller execution!")
        print(e.stderr)
        print("==================================================")
        sys.exit(1)

if __name__ == "__main__":
    build()
