import argparse
import os
import json
import piexif
from PIL import Image
import subprocess
from tqdm import tqdm
from datetime import datetime

ARG_FOLDER_JSON: str | None = None
ARG_FOLDER_MEDIA: str | None = None

CHANGE_SUCCESSFUL = "SUCCESS"
CHANGE_FAILED = "FAILURE"
NO_CHANGE_ATTEMPTED = "NO_ATTEMPT"
EXIFTOOL_CANDIDATE = "EXIFTOOL_CANDIDATE"

def format_exif_datetime(timestamp_str: str) -> str | None:
    try:
        dt_object = datetime.fromtimestamp(int(timestamp_str))
        return dt_object.strftime("%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError) as e:
        tqdm.write(f"    WARN: Could not convert timestamp '{timestamp_str}' to datetime: {e}")
        return None

def folder_to_list() -> list[str]:
  folder_path = ARG_FOLDER_MEDIA
  if folder_path is None:
    tqdm.write("Error: Media folder path (ARG_FOLDER_MEDIA) has not been initialized.")
    return []

  files_in_folder = []
  if os.path.isdir(folder_path):
    try:
      for item in os.listdir(folder_path):
        if os.path.isfile(os.path.join(folder_path, item)):
          files_in_folder.append(item)
      if not files_in_folder:
        tqdm.write(f"No files found in {folder_path}")
    except OSError as e:
      tqdm.write(f"Error accessing {folder_path}: {e}")
  else:
    tqdm.write(f"\nError: Folder '{folder_path}' not found or is not a directory.")
  return files_in_folder

def folder_to_dict() -> dict[str, str]:
  folder_path = ARG_FOLDER_JSON
  if folder_path is None:
    tqdm.write("Error: JSON folder path (ARG_FOLDER_JSON) has not been initialized.")
    return {}

  json_file_map: dict[str, str] = {}
  if os.path.isdir(folder_path):
    try:
      for item_name in os.listdir(folder_path):
        if os.path.isfile(os.path.join(folder_path, item_name)):
          item_split = item_name.split(".", 2)
          if len(item_split) == 3 and item_split[2].lower().endswith(".json"):
            key = f"{item_split[0]}.{item_split[1]}"
            json_file_map[key.lower()] = item_name
          else:
            tqdm.write(f"WARN: Unrecognized JSON file naming pattern: {item_name}. Could not determine key.")
    except OSError as e:
      tqdm.write(f"Error accessing JSON folder {folder_path}: {e}")
  else:
    tqdm.write(f"\nError: JSON Folder '{folder_path}' not found or is not a directory.")
  return json_file_map

def edit_image_photo_taken_time(image_filename: str, json_data: dict) -> tuple[str, dict | None]:
    if ARG_FOLDER_MEDIA is None:
        tqdm.write(f"  Error: Media folder path not set. Cannot process {image_filename}.")
        return NO_CHANGE_ATTEMPTED, None

    image_full_path = os.path.join(ARG_FOLDER_MEDIA, image_filename)
    if not os.path.isfile(image_full_path):
        tqdm.write(f"  Error: Image file not found: {image_full_path}")
        return NO_CHANGE_ATTEMPTED, None

    photo_taken_time_data = json_data.get("photoTakenTime")
    if not isinstance(photo_taken_time_data, dict):
        tqdm.write(f"    INFO: 'photoTakenTime' data not found or not a dictionary in JSON for {image_filename}.")
        return NO_CHANGE_ATTEMPTED, None

    timestamp_str = photo_taken_time_data.get("timestamp")
    if not timestamp_str:
        tqdm.write(f"    INFO: 'timestamp' not found in 'photoTakenTime' for {image_filename}.")
        return NO_CHANGE_ATTEMPTED, None

    exif_datetime_str = format_exif_datetime(timestamp_str)
    if not exif_datetime_str:
        return NO_CHANGE_ATTEMPTED, None

    file_extension = os.path.splitext(image_filename)[1].lower()
    attempt_made_and_succeeded = False

    if file_extension in [".jpg", ".jpeg"]:
        try:
            exif_dict = piexif.load(image_full_path)
        except piexif.InvalidImageDataError:
            tqdm.write(f"  WARN: No EXIF data in JPEG {image_filename} or unsupported. Creating new EXIF structure.")
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}, "thumbnail": None}
        except Exception as e:
            tqdm.write(f"  Error loading EXIF from JPEG {image_filename}: {e}")
            return CHANGE_FAILED, None

        if "Exif" not in exif_dict:
            exif_dict["Exif"] = {}
        
        exif_datetime_bytes = exif_datetime_str.encode('utf-8')
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = exif_datetime_bytes
        exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = exif_datetime_bytes
        
        try:
            exif_bytes_to_save = piexif.dump(exif_dict)
            img = Image.open(image_full_path)
            img.save(image_full_path, exif=exif_bytes_to_save)
            attempt_made_and_succeeded = True
        except ValueError as e:
             tqdm.write(f"    Error dumping EXIF data for JPEG {image_filename}: {e}")
             return CHANGE_FAILED, None
        except Exception as e:
            tqdm.write(f"    Error saving JPEG {image_filename} with new EXIF: {e}")
            return CHANGE_FAILED, None
        
        return (CHANGE_SUCCESSFUL if attempt_made_and_succeeded else CHANGE_FAILED), None

    elif file_extension in [".heic", ".mov", ".mp4", ".png"]:
        exiftool_data = {
            "full_path": image_full_path,
            "datetime_str": exif_datetime_str,
            "file_type": file_extension.strip(".")
        }
        return EXIFTOOL_CANDIDATE, exiftool_data

    else:
        tqdm.write(f"    INFO: File type {file_extension} for {image_filename} is not currently supported for datetime modification by this script.")
        return NO_CHANGE_ATTEMPTED, None

def _run_batch_exiftool_processing(exiftool_candidates: list[dict]) -> tuple[int, int]:
    if not exiftool_candidates:
        return 0, 0

    tqdm.write(f"\nStarting batch ExifTool processing for {len(exiftool_candidates)} files...")
    
    base_tags_map = {
        "heic": ["-EXIF:DateTimeOriginal", "-QuickTime:CreationDate", "-Keys:CreationDate"],
        "mov": ["-QuickTime:CreateDate", "-Keys:CreationDate", "-Track1:CreateDate", "-UserData:DateTimeOriginal"],
        "mp4": ["-QuickTime:CreateDate", "-Keys:CreationDate", "-TrackCreateDate", "-MediaCreateDate", "-UserData:DateTimeOriginal"],
        "png": ["-EXIF:DateTimeOriginal", "-PNG:CreationTime", "-XMP:DateTimeOriginal", "-CreateDate"]
    }
    
    MAX_FILES_PER_BATCH = 50
    succeeded_count = 0
    failed_count = 0

    with tqdm(total=len(exiftool_candidates), desc="Batch ExifTool Processing", unit="file") as pbar_batch:
        for i in range(0, len(exiftool_candidates), MAX_FILES_PER_BATCH):
            batch_subset = exiftool_candidates[i:i+MAX_FILES_PER_BATCH]
            command = ["exiftool", "-overwrite_original_in_place", "-m"]
            
            files_in_current_batch_names = [os.path.basename(item["full_path"]) for item in batch_subset]
            tqdm.write(f"  Starting ExifTool sub-batch {i//MAX_FILES_PER_BATCH + 1} (up to {len(batch_subset)} files): {', '.join(files_in_current_batch_names[:3])}...")

            for item in batch_subset:
                chosen_tags = base_tags_map.get(item["file_type"], ["-DateTimeOriginal", "-CreateDate"])
                for tag_name in chosen_tags:
                    command.append(f"{tag_name}={item['datetime_str']}")
                command.append(item["full_path"])
            
            try:
                result = subprocess.run(command, capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    succeeded_count += len(batch_subset)
                else:
                    failed_count += len(batch_subset)
                    tqdm.write(f"    ExifTool Batch Error (Return Code: {result.returncode}) for files ~{files_in_current_batch_names[0]}:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
            except FileNotFoundError:
                tqdm.write("    ExifTool Error: 'exiftool' command not found. All files in this batch failed.")
                failed_count += len(batch_subset)
                break
            except Exception as e:
                tqdm.write(f"    An unexpected error occurred while running ExifTool batch: {e}. All files in this batch failed.")
                failed_count += len(batch_subset)
            pbar_batch.update(len(batch_subset))
            
    tqdm.write(f"Batch ExifTool processing finished. Success: {succeeded_count}, Failed: {failed_count}")
    return succeeded_count, failed_count

def main():
  global ARG_FOLDER_JSON, ARG_FOLDER_MEDIA

  parser = argparse.ArgumentParser(
      description="Apply 'photoTakenTime' from JSON files to corresponding media file EXIF data."
  )
  parser.add_argument("folder_json", help="Path to the folder of JSON files (e.g., 'IMG_0493.JPG.json')")
  parser.add_argument("folder_media", help="Path to the folder of media files (e.g., 'IMG_0493.JPG')")

  args = parser.parse_args()

  ARG_FOLDER_JSON = args.folder_json
  ARG_FOLDER_MEDIA = args.folder_media

  print(f"JSON folder: {ARG_FOLDER_JSON}")
  print(f"Media folder: {ARG_FOLDER_MEDIA}")
  print("---")
  print("IMPORTANT: This script will OVERWRITE media files in the media folder with new metadata.")
  print("For HEIC/MOV/MP4/PNG files, ExifTool must be installed and in your system PATH.")
  print("Please BACKUP your media files before proceeding!")
  print("---\n")


  json_files_map = folder_to_dict()
  media_files_list = folder_to_list()

  if not json_files_map:
    print("No JSON files found or processed into map in the JSON folder. Exiting.")
    return
  if not media_files_list:
    print("No media files found in the media folder. Exiting.")
    return

  print(f"Found {len(json_files_map)} mappable JSON entries.")
  print(f"Found {len(media_files_list)} media files to process.\n")

  files_to_change_count = 0
  files_successfully_changed_count = 0
  files_failed_to_change_count = 0
  files_skipped_json_issue_count = 0
  exiftool_candidates_list = []

  with tqdm(media_files_list, desc="Processing media files", unit="file") as pbar:
    for media_filename in pbar:
      pbar.set_postfix_str(f"Current: {media_filename}", refresh=True)
      media_filename_lower = media_filename.lower()
      original_json_filename = json_files_map.get(media_filename_lower)
      match_type = "direct"

      if original_json_filename is None:
          media_base, media_ext_lower = os.path.splitext(media_filename_lower)
          if media_ext_lower == ".mp4":
              for json_map_key, mapped_json_filename in json_files_map.items():
                  json_map_base, _ = os.path.splitext(json_map_key)
                  if json_map_base == media_base:
                      original_json_filename = mapped_json_filename
                      match_type = f"fallback (video using JSON key: {json_map_key})"
                      break

      if original_json_filename:
        json_full_path = os.path.join(ARG_FOLDER_JSON, original_json_filename)
        
        try:
          with open(json_full_path, 'r', encoding='utf-8') as f:
            data_from_json = json.load(f)
          
          if isinstance(data_from_json, dict):
            status, exiftool_data = edit_image_photo_taken_time(media_filename, data_from_json)
            
            if status == EXIFTOOL_CANDIDATE and exiftool_data:
                exiftool_candidates_list.append(exiftool_data)
                files_to_change_count +=1
            elif status == CHANGE_SUCCESSFUL:
                files_to_change_count +=1
                files_successfully_changed_count += 1
            elif status == CHANGE_FAILED:
                files_to_change_count +=1
                files_failed_to_change_count += 1
                tqdm.write(f"Failed to process JPEG: {media_filename} (JSON: {original_json_filename}, Match: {match_type}). Reason logged above.")
          else:
            tqdm.write(f"  WARN: Content of {original_json_filename} is not a dictionary. Skipping {media_filename}.")
            files_skipped_json_issue_count += 1
        except FileNotFoundError:
          tqdm.write(f"  Error: JSON file {json_full_path} not found though listed in map. Skipping {media_filename}.")
          files_skipped_json_issue_count += 1
        except json.JSONDecodeError as e:
          tqdm.write(f"  Error: Could not decode JSON from {json_full_path}: {e}. Skipping {media_filename}.")
          files_skipped_json_issue_count += 1
        except Exception as e:
          tqdm.write(f"  Error processing {media_filename} with {original_json_filename}: {e}. Skipping.")
          files_skipped_json_issue_count += 1
      else:
        tqdm.write(f"No corresponding JSON file found in map for media: {media_filename}. Skipping.")
        files_skipped_json_issue_count += 1

  if exiftool_candidates_list:
      et_success, et_failed = _run_batch_exiftool_processing(exiftool_candidates_list)
      files_successfully_changed_count += et_success
      files_failed_to_change_count += et_failed

  print("\n--- Processing Complete ---")
  print(f"Total media files scanned: {len(media_files_list)}")
  print(f"Media files identified for change (valid photoTakenTime found): {files_to_change_count}")
  print(f"Media files successfully changed: {files_successfully_changed_count}")
  print(f"Media files failed to change (attempt made but failed): {files_failed_to_change_count}")
  print(f"Media files skipped (no JSON match, JSON error, or no valid photoTakenTime): {len(media_files_list) - files_to_change_count}")

if '__main__' == __name__:
  main()
