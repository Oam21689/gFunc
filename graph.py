import os
import ast
import webbrowser
from graphviz import Digraph
from collections import defaultdict
import sys


def extract_classes_with_nested_models(file_path):
    """
    Parse a Python file to extract class definitions with their attributes, types, and nested models.
    Handles nested structures like List[Model], Optional[Model].
    """
    classes = {}
    base_models = set()
    nested_relationships = []
    file_to_class_map = {}

    def resolve_type(annotation):
        """
        Resolve the type from the annotation node, handling cases like List[Model], Optional[Model].
        """
        if isinstance(annotation, ast.Name):
            return annotation.id  # e.g., str, int, Model
        elif isinstance(annotation, ast.Subscript):
            # Handle List[Model] or Optional[Model]
            if isinstance(annotation.value, ast.Name):
                container_type = annotation.value.id
                if container_type in {"List", "Optional", "Dict"} and hasattr(annotation, "slice"):
                    # Extract inner type
                    if isinstance(annotation.slice, ast.Name):
                        return f"{container_type}[{annotation.slice.id}]"
                    elif isinstance(annotation.slice, ast.Subscript):
                        return f"{container_type}[{resolve_type(annotation.slice)}]"
                    elif isinstance(annotation.slice, ast.Attribute):
                        return f"{container_type}[{annotation.slice.attr}]"
            return "ComplexType"
        elif isinstance(annotation, ast.Attribute):
            return annotation.attr  # Handles cases like pydantic.BaseModel
        return "Unknown"

    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

        # Collect all class definitions first
        class_definitions = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}

        for class_name, node in class_definitions.items():
            attributes = []
            is_base_model = False

            # Record the file where the class was defined
            file_to_class_map[class_name] = file_path

            # Check for inheritance
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "BaseModel":
                    is_base_model = True
                elif isinstance(base, ast.Attribute) and base.attr == "BaseModel":
                    is_base_model = True

            # Extract attributes and detect nested models
            for child in node.body:
                if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                    attr_name = child.target.id
                    attr_type = resolve_type(child.annotation)

                    # Detect if attr_type is another class (nested model)
                    inner_model = None
                    if "[" in attr_type:  # Handle List[Model] or similar
                        inner_model = attr_type.split("[")[-1].rstrip("]")
                    elif attr_type in class_definitions:
                        inner_model = attr_type

                    if inner_model:
                        nested_relationships.append((class_name, attr_name, inner_model))
                        attributes.append((attr_name, attr_type, True))  # Highlight nested
                    else:
                        attributes.append((attr_name, attr_type, False))  # Normal

            classes[class_name] = attributes
            if is_base_model:
                base_models.add(class_name)

    return classes, base_models, nested_relationships, file_to_class_map


def analyze_models_folder(models_folder):
    """
    Analyze all Python files in a folder to extract class definitions, attributes, and relationships.
    """
    all_classes = {}
    all_base_models = set()
    all_relationships = []
    class_to_file_map = {}

    # Walk through all Python files in the folder
    for root, _, files in os.walk(models_folder):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                classes, base_models, relationships, file_map = extract_classes_with_nested_models(file_path)

                # Merge data into global structures
                all_classes.update(classes)
                all_base_models.update(base_models)
                all_relationships.extend(relationships)
                class_to_file_map.update(file_map)

    return all_classes, all_base_models, all_relationships, class_to_file_map


def normalize_type(attr_type):
    """
    Normalize types for comparison:
    - Remove 'Optional' or 'List' wrappers.
    - Only compare the core type.
    """
    if "[" in attr_type:
        return attr_type.split("[")[1].rstrip("]")
    return attr_type


def find_inconsistent_attributes(classes, class_to_file_map):
    """
    Find attributes with the same name but different core types across classes.
    """
    attribute_types = defaultdict(set)  # Map attribute names to a set of their normalized types
    attribute_files = defaultdict(list)  # Map attribute names to the files where they appear

    for class_name, attributes in classes.items():
        for attr_name, attr_type, _ in attributes:
            normalized_type = normalize_type(attr_type)
            attribute_types[attr_name].add(normalized_type)
            attribute_files[attr_name].append(class_to_file_map[class_name])

    # Identify inconsistencies
    inconsistent_attributes = {name for name, types in attribute_types.items() if len(types) > 1}
    inconsistency_summary = {
        name: {"types": types, "files": set(attribute_files[name])}
        for name, types in attribute_types.items()
        if len(types) > 1
    }
    return inconsistent_attributes, inconsistency_summary


def save_html_report(inconsistency_summary, output_dir="visual"):
    """
    Save the inconsistency summary to an HTML file and open it in the default browser.
    """
    # Create visual directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    template_file = "template.html"
    output_file = os.path.join(output_dir, "inconsistencies_report.html")

    if not os.path.exists(template_file):
        print(f"Template file '{template_file}' not found.")
        return

    # Read the template file
    with open(template_file, "r", encoding="utf-8") as template:
        html_content = template.read()

    # Generate table rows dynamically
    table_rows = ""
    attributes = []
    type_labels = set()
    type_data = defaultdict(lambda: [0] * len(inconsistency_summary))

    for index, (attr_name, details) in enumerate(inconsistency_summary.items()):
        attributes.append(attr_name)

        # Prepare data for each type
        for t in details['types']:
            type_labels.add(t)
            type_data[t][index] += 1

        # Replace commas with <br> for new lines in the Files column
        formatted_files = "<br>".join(details['files'])
        table_rows += f"""
            <tr>
                <td>{attr_name}</td>
                <td>{', '.join(details['types'])}</td>
                <td>{formatted_files}</td>
            </tr>
        """

    # Convert type labels and data into sorted lists for Chart.js
    type_labels = list(type_labels)
    datasets = []
    colors = ["rgba(75, 192, 192, 0.7)", "rgba(255, 99, 132, 0.7)", "rgba(54, 162, 235, 0.7)", "rgba(255, 206, 86, 0.7)", "rgba(153, 102, 255, 0.7)"]

    for i, type_label in enumerate(type_labels):
        datasets.append({
            "label": type_label,
            "data": type_data[type_label],
            "backgroundColor": colors[i % len(colors)],
        })

    # Insert Chart.js data
    chart_data = f"""
        const labels = {attributes};
        const data = {{
            labels: labels,
            datasets: {datasets}
        }};
    """

    # Replace the placeholders in the template with the actual table rows and chart data
    html_content = html_content.replace("{{TABLE_ROWS}}", table_rows)
    html_content = html_content.replace("{{CHART_DATA}}", chart_data)

    # Write the populated HTML content to the output file
    with open(output_file, "w", encoding="utf-8") as html_file:
        html_file.write(html_content)

    # Open the file in the default web browser
    webbrowser.open(f"file://{os.path.abspath(output_file)}")
    print(f"HTML report saved to {output_file} and opened in the browser.")




def generate_inconsistent_model_diagram(classes, relationships, inconsistent_attributes, output_dir="visual"):
    """
    Generate a visually appealing diagram highlighting inconsistencies across the folder.
    """
    # Create visual directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, "folder_model_diagram")
    dot = Digraph(comment="Folder-Wide Model Diagram")

    # Define graph attributes for a clean layout
    dot.attr(rankdir="LR", splines="spline", nodesep="1", ranksep="1.2")

    # Add nodes for classes with styling
    for class_name, attributes in classes.items():
        label = f"<<TABLE BORDER='0' CELLBORDER='1' CELLSPACING='0'>"
        label += f"<TR><TD BGCOLOR='lightblue'><B>{class_name}</B></TD></TR>"
        for attr_name, attr_type, is_nested in attributes:
            if attr_name in inconsistent_attributes:
                label += f"<TR><TD ALIGN='LEFT' BGCOLOR='#FFC0C0'><B>{attr_name}: {attr_type}</B></TD></TR>"
            elif is_nested:
                label += f"<TR><TD ALIGN='LEFT' BGCOLOR='lightyellow'><B>{attr_name}: {attr_type}</B></TD></TR>"
            else:
                label += f"<TR><TD ALIGN='LEFT'>{attr_name}: {attr_type}</TD></TR>"
        label += "</TABLE>>"
        dot.node(class_name, label=label, shape="plaintext")

    # Add arrows for nested relationships with styling
    for parent, attr_name, child in relationships:
        dot.edge(parent, child, label=f"{attr_name}", color="darkgreen", arrowhead="vee", arrowsize="1")

    # Save and render the diagram
    dot.render(output_file, format="png", cleanup=True)
    print(f"Folder-wide diagram saved as {output_file}.png")


def generate_python_file_diagram(file_path, output_dir="visual"):
    """
    Generate a diagram showing all classes and functions in a Python file.
    Using consistent styling with the folder-wide diagram.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    output_file = os.path.join(output_dir, f"python_{file_name}")
    
    dot = Digraph(comment=f"Python File Structure: {file_name}")
    # Match the folder diagram styling
    dot.attr(rankdir="LR", splines="spline", nodesep="1", ranksep="1.2")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        # Add file node with consistent styling
        dot.node(file_name, label=f"<<B>{file_name}.py</B>>", 
                shape="folder", style="filled", fillcolor="lightgrey")

        # Track all nodes for connecting later
        classes = {}
        functions = {}
        
        # First pass: collect all classes and functions
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_label = f"<<TABLE BORDER='0' CELLBORDER='1' CELLSPACING='0'>"
                class_label += f"<TR><TD BGCOLOR='lightblue'><B>{node.name}</B></TD></TR>"
                
                # Add methods with consistent styling
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        # Methods get lightyellow background like nested attributes
                        class_label += f"<TR><TD ALIGN='LEFT' BGCOLOR='lightyellow'>{item.name}()</TD></TR>"
                
                class_label += "</TABLE>>"
                classes[node.name] = node
                dot.node(f"class_{node.name}", label=class_label, shape="plaintext")
                dot.edge(file_name, f"class_{node.name}", 
                        color="darkgreen", arrowhead="vee", arrowsize="1")

            elif isinstance(node, ast.FunctionDef):
                # Style standalone functions with a consistent look
                func_label = f"<<TABLE BORDER='0' CELLBORDER='1' CELLSPACING='0'>"
                func_label += f"<TR><TD BGCOLOR='lightblue'><B>{node.name}()</B></TD></TR>"
                func_label += "</TABLE>>"
                functions[node.name] = node
                dot.node(f"func_{node.name}", label=func_label, shape="plaintext")
                dot.edge(file_name, f"func_{node.name}", 
                        color="darkgreen", arrowhead="vee", arrowsize="1")

        # Second pass: add inheritance relationships
        for class_name, node in classes.items():
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_name = base.id
                    if base_name in classes:  # Only connect if base class is in the same file
                        dot.edge(f"class_{base_name}", f"class_{class_name}", 
                               style="dashed", color="darkgreen", arrowhead="empty")

        dot.render(output_file, format="png", cleanup=True)
        print(f"Python file structure diagram saved as {output_file}.png")
        
    except Exception as e:
        print(f"Error generating diagram for {file_path}: {str(e)}")

# Replace the hardcoded analysis section at the bottom with:
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python graph.py <models_folder_path>")
        sys.exit(1)

    models_folder = sys.argv[1]
    output_dir = "visual"
    
    # Create visual directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Analyze the folder
    classes, base_models, relationships, class_to_file_map = analyze_models_folder(models_folder)

    # Find inconsistent attributes
    inconsistent_attributes, inconsistency_summary = find_inconsistent_attributes(classes, class_to_file_map)

    # Save the inconsistency summary to an HTML file and display it in a browser
    save_html_report(inconsistency_summary, output_dir)

    # Generate the folder-wide diagram
    generate_inconsistent_model_diagram(classes, relationships, inconsistent_attributes, output_dir)
    
    # Process all Python files in the folder
    for root, _, files in os.walk(models_folder):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                # Generate Python structure diagram for all Python files
                generate_python_file_diagram(file_path, output_dir)