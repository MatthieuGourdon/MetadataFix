# Media Metadata Fixer

This script updates the "photo taken time" metadata of media files (JPEG, HEIC, MOV, MP4, PNG) based on corresponding JSON metadata files.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

1.  **Python 3.7+**: You can download Python from [python.org](https://www.python.org/).
2.  **ExifTool**: This is a command-line application used for reading and writing meta information in a wide variety of files.
    *   **Linux (Debian/Ubuntu)**: `sudo apt install libimage-exiftool-perl`
    *   **macOS (using Homebrew)**: `brew install exiftool`
    *   **Windows & other systems**: Download from the ExifTool website. Ensure `exiftool.exe` (or `exiftool`) is in your system's PATH or place it in the same directory as the script.

## Setup Instructions

Follow these steps to set up the Python environment for the script:

1.  **Clone the Script**:
    ```bash
    git clone git@github.com:MatthieuGourdon/MetadataFix.git
    cd MetadataFix
    ```

2.  **Create and Activate a Virtual Environment**:

    *   **Linux and macOS**:
        Open your terminal and run:
        ```bash
        python3 -m venv .venv
        source .venv/bin/activate
        ```
        Your terminal prompt should now indicate that the virtual environment (`.venv`) is active.

    *   **Windows (Command Prompt)**:
        Open Command Prompt and run:
        ```bash
        python -m venv .venv
        .venv\Scripts\activate.bat
        ```
        Your command prompt should now indicate that the virtual environment (`.venv`) is active.

    *   **Windows (PowerShell)**:
        Open PowerShell and run:
        ```bash
        python -m venv .venv
        .venv\Scripts\Activate.ps1
        ```
        If you get an error about script execution being disabled, you might need to change the execution policy for the current session:
        ```powershell
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
        ```
        Then try activating again. Your PowerShell prompt should now indicate that the virtual environment (`.venv`) is active.

3.  **Install Dependencies**:
    Once the virtual environment is activated, install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

## Running the Script

After setting up the environment and ensuring ExifTool is installed, you can run the script from your terminal (while the virtual environment is active).

#### /!\ Ensure that the .json file are properly named, it should be FILE_NAME.EXT.[...].json /!\

**Command Structure:**

```bash
python metadata_fix.py /path/to/your/json_folder /path/to/your/media_folder
