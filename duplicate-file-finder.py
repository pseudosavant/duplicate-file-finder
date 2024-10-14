"""
MIT License

Copyright (c) 2024 Paul Ellis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import os
import sys
import hashlib
import argparse
from collections import defaultdict
import time
import csv
import json
from datetime import datetime
import fnmatch

def check_dependencies():
    missing_dependencies = []
    
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
    except ImportError:
        missing_dependencies.append("futures")  # For Python 2 compatibility
    
    try:
        import tqdm
    except ImportError:
        missing_dependencies.append("tqdm")
    
    if missing_dependencies:
        print("The following required dependencies are missing:")
        for dep in missing_dependencies:
            print(f"  - {dep}")
        print("\nTo install the required dependencies, run the following command:")
        print(f"pip install {' '.join(missing_dependencies)}")
        print("\nAfter installing the dependencies, please run the script again.")
        sys.exit(1)

def get_file_hash(filepath):
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as file:
            buf = file.read(65536)  # Read in 64k chunks
            while len(buf) > 0:
                hasher.update(buf)
                buf = file.read(65536)
        return hasher.hexdigest()
    except IOError:
        print(f"Error reading file: {filepath}")
        return None

def get_file_info(filepath):
    try:
        stats = os.stat(filepath)
        return (stats.st_ctime, stats.st_mtime, os.path.abspath(filepath), stats.st_size)
    except OSError:
        print(f"Error accessing file: {filepath}")
        return None

def should_include_file(filepath, exclude_keywords):
    return not any(keyword.lower() in filepath.lower() for keyword in exclude_keywords)

def format_date(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def parse_size(size_str):
    if not size_str:
        return 0  # Default to 0 bytes if no size is specified
    
    size_str = size_str.strip().upper()
    if size_str == '0' or size_str == '0B':
        return 0
    
    units = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
    
    # Check if the size string ends with a valid unit
    unit = next((u for u in units if size_str.endswith(u)), 'B')
    
    try:
        # Remove the unit from the string and convert to float
        number = float(size_str[:-len(unit)] if unit != 'B' else size_str)
        return int(number * units[unit])
    except ValueError:
        print(f"Invalid size format: {size_str}. Using default of 0 bytes.")
        return 0

def find_duplicates(folder_path, file_pattern, current_folder_only, check_contents, verbose, exclude_keywords, min_filesize):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from tqdm import tqdm

    size_groups = defaultdict(list)
    total_files = 0
    excluded_files = 0
    total_size = 0
    
    print("Scanning files...")
    for root, _, files in os.walk(folder_path):
        if current_folder_only and root != folder_path:
            continue
        for filename in files:
            if fnmatch.fnmatch(filename, file_pattern):
                filepath = os.path.join(root, filename)
                if should_include_file(filepath, exclude_keywords):
                    file_info = get_file_info(filepath)
                    if file_info and file_info[3] >= min_filesize:
                        size_groups[file_info[3]].append(file_info)
                        total_files += 1
                        total_size += file_info[3]  # file size
                    else:
                        excluded_files += 1
                else:
                    excluded_files += 1
    
    print(f"Found {total_files} files to process. Excluded {excluded_files} files based on keywords or size.")
    duplicates = []
    duplicate_size = 0
    
    if check_contents:
        print("Calculating hashes for files with matching sizes...")
        total_files_to_hash = sum(len(group) for group in size_groups.values() if len(group) > 1)
        with tqdm(total=total_files_to_hash, unit="file") as pbar:
            for size, group in size_groups.items():
                if len(group) > 1:
                    file_hashes = defaultdict(list)
                    with ThreadPoolExecutor() as executor:
                        future_to_filepath = {executor.submit(get_file_hash, file_info[2]): file_info for file_info in group}
                        for future in as_completed(future_to_filepath):
                            file_info = future_to_filepath[future]
                            try:
                                file_hash = future.result()
                                if file_hash:
                                    file_hashes[file_hash].append(file_info)
                            except Exception as exc:
                                print(f"Error processing {file_info[2]}: {exc}")
                            finally:
                                pbar.update(1)
                    
                    for file_hash, hash_group in file_hashes.items():
                        if len(hash_group) > 1:
                            sorted_group = sorted(hash_group)
                            original = sorted_group[0]
                            duplicates.extend([(filepath, original) for filepath in sorted_group[1:]])
                            duplicate_size += size * (len(hash_group) - 1)
                            if verbose:
                                print(f"Found {len(hash_group)} duplicate files with hash {file_hash[:8]}...")
    else:
        print("Checking for size duplicates...")
        for size, group in size_groups.items():
            if len(group) > 1:
                sorted_group = sorted(group)
                original = sorted_group[0]
                duplicates.extend([(filepath, original) for filepath in sorted_group[1:]])
                duplicate_size += size * (len(group) - 1)
                if verbose:
                    print(f"Found {len(group)} files with size {size} bytes")
    
    return duplicates, total_files, len(duplicates), duplicate_size, total_size

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0

def parse_exclude_keywords(exclude_arg):
    if not exclude_arg:
        return []
    return [keyword.strip() for keyword in exclude_arg.split(',') if keyword.strip()]

def write_csv(duplicates, csv_file):
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Duplicate Filepath', 'Original Filepath', 'Filesize (bytes)', 'Last Modified Date', 'Creation Date'])
        for duplicate, original in duplicates:
            dup_ctime, dup_mtime, dup_path, dup_size = duplicate
            orig_ctime, orig_mtime, orig_path, _ = original
            writer.writerow([
                dup_path,
                orig_path,
                dup_size,
                format_date(dup_mtime),
                format_date(dup_ctime)
            ])

def write_json(duplicates, json_file):
    json_data = []
    for duplicate, original in duplicates:
        dup_ctime, dup_mtime, dup_path, dup_size = duplicate
        orig_ctime, orig_mtime, orig_path, _ = original
        json_data.append({
            "Duplicate Filepath": dup_path,
            "Original Filepath": orig_path,
            "Filesize (bytes)": dup_size,
            "Last Modified Date": format_date(dup_mtime),
            "Creation Date": format_date(dup_ctime)
        })
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2)

def main():
    try:
        check_dependencies()

        parser = argparse.ArgumentParser(description="Find duplicate files in a directory.")
        parser.add_argument("--dir", "-d", default='.', help="Directory to search in (default: current directory)")
        parser.add_argument("--pattern", "-p", default='*', help="File pattern to search for (e.g., '*.jpg', 'img-*.png') (default: * for all files)")
        parser.add_argument("--current-folder-only", action="store_true", help="Search only in the current folder")
        parser.add_argument("--check-contents", action="store_true", help="Perform content hash check to verify duplicates")
        parser.add_argument("-v", "--verbose", action="store_true", help="Increase output verbosity")
        parser.add_argument("--output", "-o", help="Specify an output file for the list of duplicates")
        parser.add_argument("--exclude", help="Comma-separated list of keywords to exclude files containing these in their path")
        parser.add_argument("--csv", help="Specify a CSV file to output detailed duplicate information")
        parser.add_argument("--json", help="Specify a JSON file to output detailed duplicate information")
        parser.add_argument("--min-filesize", default="0B", help="Minimum file size to consider (e.g., 10MB, 1GB)")
        parser.add_argument("--quiet", "-q", action="store_true", help="Suppress printing of individual matches")
        
        args = parser.parse_args()

        exclude_keywords = parse_exclude_keywords(args.exclude)
        min_filesize = parse_size(args.min_filesize)
        
        if not args.quiet:
            print(f"Searching for duplicates in {os.path.abspath(args.dir)}")
            print(f"File pattern: {args.pattern}")
            print(f"Current folder only: {args.current_folder_only}")
            print(f"Checking file contents: {args.check_contents}")
            print(f"Minimum file size: {format_size(min_filesize)}")
            if exclude_keywords:
                print(f"Excluding files with these keywords: {', '.join(exclude_keywords)}")
        
        start_time = time.time()
        duplicates, total_files, duplicate_count, duplicate_size, total_size = find_duplicates(
            args.dir, args.pattern, args.current_folder_only, args.check_contents, args.verbose, exclude_keywords, min_filesize
        )
        end_time = time.time()
        duration = end_time - start_time
        
        if duplicates:
            if not args.quiet:
                print(f"\nFound {duplicate_count} duplicate files:")
                for duplicate, original in duplicates:
                    print(f"{duplicate[2]} ({original[2]})")
            
            if args.output:
                with open(args.output, 'w') as f:
                    for duplicate, _ in duplicates:
                        f.write(f"{duplicate[2]}\n")
                if not args.quiet:
                    print(f"\nList of duplicates has been saved to {args.output}")
            
            if args.csv:
                write_csv(duplicates, args.csv)
                if not args.quiet:
                    print(f"\nDetailed duplicate information has been saved to {args.csv}")
            
            if args.json:
                write_json(duplicates, args.json)
                if not args.quiet:
                    print(f"\nDetailed duplicate information has been saved to {args.json}")
        else:
            if not args.quiet:
                print("No duplicates found.")
        
        print("\nSummary Statistics:")
        print(f"Total files checked: {total_files}")
        print(f"Total duplicate files: {duplicate_count}")
        print(f"Total size of duplicate files: {format_size(duplicate_size)}")
        print(f"Total size of all files: {format_size(total_size)}")
        print(f"Duration of duplicate check: {duration:.2f}s")

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        print("If this error persists, please report it to the script maintainer.")
        sys.exit(1)

if __name__ == "__main__":
    main()