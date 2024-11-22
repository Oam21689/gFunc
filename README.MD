# gFunc: Python Function and Attribute Inconsistency Analyzer

gFunc is a Python analysis tool designed to identify inconsistencies in attribute types and visualize relationships between functions and classes across a folder of Python files. It generates detailed reports and diagrams to aid in debugging and understanding complex codebases.

## Features

### Attribute Inconsistency Detection:
Identifies attributes with conflicting types across multiple classes.
- Highlights the specific files where inconsistencies occur.

### HTML Report:
- Interactive, styled HTML report summarizing inconsistencies.
- Includes a bar chart visualizing the occurrences of inconsistencies.
- Option to download the report as a PDF.

### Folder-Wide Model Diagram:
- Generates a diagram visualizing class structures and highlighting inconsistencies.
- Clearly marks relationships and nested attributes.

## Output

### HTML Report:
- Displays inconsistencies in a table with conflicting types and file locations.
- Visualizes inconsistencies using Chart.js.
- Allows exporting the report as a PDF via a built-in button.

### Folder-Wide Diagram:
- Saves a .png file highlighting class structures and attribute inconsistencies using Graphviz.

## Requirements

Ensure you have the following installed:

- Python 3.8 or higher
- Required Python libraries:
  - graphviz
  - webbrowser

Install the Python dependencies with:

```bash
pip install graphviz webbrowser
```
## Installation

1. Clone the repository:

```bash
git clone https://github.com/oam21689/gFunc.git
cd gFunc
```
2. ensure the template file is in the same directory as the script.

Usage
```bash
python gFunc.py <Folder>
```
## Example:
if the project folder is structured as follows:

```
project/
├── models/
│   ├── file1.py
│   └── file2.py
```

```bash
python gFunc.py models/
```
