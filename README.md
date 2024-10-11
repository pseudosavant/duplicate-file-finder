# Duplicate File Finder

This Python script helps you find duplicate files in a specified directory. It offers various options for customizing the search, including file size filtering, content checking, and output formats.

## Features

- Search for duplicates based on file size or content
- Specify minimum file size to consider
- Exclude files based on keywords in their path
- Output results to console, text file, CSV, or JSON
- Quiet mode for suppressing individual match output

## Requirements

- Python 3.x
- `tqdm` library (for progress bars)

## Installation

1. Clone this repository or download the `duplicate-file-finder.py` script.
2. Install the required dependencies:

```
pip install tqdm
```

## Usage

Run the script from the command line:

```
python duplicate-file-finder.py [options]
```

### Options

- `--dir`, `-d`: Directory to search in (default: current directory)
- `--pattern`, `-p`: File pattern to search for (e.g., '*.jpg', 'img-*.png') (default: * for all files)
- `--current-folder-only`: Search only in the current folder
- `--check-contents`: Perform content hash check to verify duplicates
- `-v`, `--verbose`: Increase output verbosity
- `--output`, `-o`: Specify an output file for the list of duplicates
- `--exclude`: Comma-separated list of keywords to exclude files containing these in their path
- `--csv`: Specify a CSV file to output detailed duplicate information
- `--json`: Specify a JSON file to output detailed duplicate information
- `--min-filesize`: Minimum file size to consider (e.g., 10MB, 1GB)
- `--quiet`, `-q`: Suppress printing of individual matches

### Examples

1. Find duplicates of all files 20MB or larger in the current directory:
   ```
   python duplicate-file-finder.py --min-filesize=20MB
   ```

2. Find duplicates of PNG files in a specific directory, checking file contents:
   ```
   python duplicate-file-finder.py --dir=/path/to/directory --pattern=*.png --check-contents
   ```

3. Find duplicates and output to a CSV file, excluding files with "backup" in their path:
   ```
   python duplicate-file-finder.py --csv=duplicates.csv --exclude=backup
   ```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
