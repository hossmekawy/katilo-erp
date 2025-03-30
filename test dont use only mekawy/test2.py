import sqlite3
import argparse
import os
import glob
import logging
import sys
import re
from collections import defaultdict

# For visualization
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.patches import FancyArrowPatch

def find_inventory_database(start_path='.', recursive=True):
    """Find the inventory.db SQLite database."""
    
    # Common SQLite file extensions for the inventory database
    patterns = ['*inventory*.db', '*inventory*.sqlite', '*inventory*.sqlite3', '*inventory*.db3']
    
    # Search for inventory database first
    for pattern in patterns:
        if recursive:
            file_pattern = os.path.join(start_path, '**', pattern)
            files = glob.glob(file_pattern, recursive=True)
        else:
            file_pattern = os.path.join(start_path, pattern)
            files = glob.glob(file_pattern)
        
        # Filter valid SQLite databases
        for file_path in files:
            if is_valid_sqlite_db(file_path):
                return file_path
    
    # If no inventory database found, look for any SQLite database
    extensions = ['*.db', '*.sqlite', '*.sqlite3', '*.db3']
    for ext in extensions:
        if recursive:
            pattern = os.path.join(start_path, '**', ext)
            files = glob.glob(pattern, recursive=True)
        else:
            pattern = os.path.join(start_path, ext)
            files = glob.glob(pattern)
        
        for file_path in files:
            if is_valid_sqlite_db(file_path):
                return file_path
    
    return None

def is_valid_sqlite_db(file_path):
    """Verify if a file is a valid SQLite database."""
    try:
        conn = sqlite3.connect(f"file:{file_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()
        return len(tables) > 0
    except (sqlite3.Error, Exception):
        return False

def get_database_schema(db_path):
    """Extract schema information from SQLite database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [table[0] for table in cursor.fetchall()]
        
        schema = {}
        foreign_keys = {}
        
        for table in tables:
            # Get table info
            cursor.execute(f"PRAGMA table_info({table});")
            columns = []
            primary_keys = []
            
            for col in cursor.fetchall():
                col_id, col_name, col_type, not_null, default_val, is_pk = col
                # Handle potential Unicode issues by ensuring strings
                col_name = str(col_name) if col_name else ""
                col_type = str(col_type) if col_type else ""
                
                columns.append({
                    'name': col_name,
                    'type': col_type,
                    'not_null': not_null == 1,
                    'primary_key': is_pk == 1
                })
                
                if is_pk == 1:
                    primary_keys.append(col_name)
            
            # Get foreign keys
            cursor.execute(f"PRAGMA foreign_key_list({table});")
            table_fks = []
            
            for fk in cursor.fetchall():
                id, seq, ref_table, from_col, to_col, on_update, on_delete, match = fk
                # Handle potential Unicode issues
                from_col = str(from_col) if from_col else ""
                ref_table = str(ref_table) if ref_table else ""
                to_col = str(to_col) if to_col else ""
                
                table_fks.append({
                    'from_col': from_col,
                    'to_table': ref_table,
                    'to_col': to_col
                })
            
            schema[table] = {
                'columns': columns,
                'primary_keys': primary_keys
            }
            
            foreign_keys[table] = table_fks
            
        conn.close()
        return schema, foreign_keys
    
    except sqlite3.Error as e:
        logging.error(f"SQLite error: {e}")
        return None, None
    except Exception as e:
        logging.error(f"Error: {e}")
        return None, None

def identify_table_groups(schema, foreign_keys):
    """Group tables based on relationships and naming patterns."""
    # Initialize a graph to analyze connections
    G = nx.Graph()
    
    # Add all tables as nodes
    for table in schema.keys():
        G.add_node(table)
    
    # Add edges based on foreign key relationships
    for table, fks in foreign_keys.items():
        for fk in fks:
            ref_table = fk['to_table']
            if ref_table in schema:  # Make sure the reference exists
                G.add_edge(table, ref_table)
    
    # First grouping strategy: based on connected components in the graph
    connected_groups = list(nx.connected_components(G))
    
    # Second grouping strategy: based on naming patterns
    pattern_groups = defaultdict(list)
    
    # Common naming patterns (adjust as needed for your database)
    patterns = [
        r'^(?P<prefix>[a-z]+)_',  # tables starting with same prefix followed by underscore
        r'^(?P<prefix>[a-z]+)',   # tables starting with same prefix
    ]
    
    for table in schema.keys():
        grouped = False
        for pattern in patterns:
            match = re.match(pattern, table)
            if match:
                prefix = match.group('prefix')
                if prefix and len(prefix) > 2:  # Avoid very short prefixes
                    pattern_groups[prefix].append(table)
                    grouped = True
                    break
        
        if not grouped:
            # Put ungrouped tables in their own group
            pattern_groups[table].append(table)
    
    # Combine strategies: use connected components first, then refine with naming patterns
    # This helps when connected components are too large
    refined_groups = []
    
    # If a connected component is too large, try to split it by naming patterns
    max_group_size = 12  # Maximum number of tables in one diagram
    
    for component in connected_groups:
        if len(component) > max_group_size:
            # This component is too large, try to split by naming
            component_tables = list(component)
            component_grouped = False
            
            # Check if tables in this component share naming patterns
            for prefix, tables in pattern_groups.items():
                common_tables = [t for t in tables if t in component_tables]
                if len(common_tables) > 1 and len(common_tables) <= max_group_size:
                    # Found a reasonable subgroup
                    refined_groups.append(common_tables)
                    for t in common_tables:
                        if t in component_tables:
                            component_tables.remove(t)
                    component_grouped = True
            
            # Add remaining tables in chunks
            while component_tables:
                chunk = component_tables[:max_group_size]
                refined_groups.append(chunk)
                component_tables = component_tables[max_group_size:]
        else:
            # This component is already a good size
            refined_groups.append(component)
    
    # Make sure each table appears in at least one group
    all_grouped_tables = set()
    for group in refined_groups:
        all_grouped_tables.update(group)
    
    ungrouped = set(schema.keys()) - all_grouped_tables
    if ungrouped:
        # Add remaining tables in manageable chunks
        ungrouped_list = list(ungrouped)
        for i in range(0, len(ungrouped_list), max_group_size):
            refined_groups.append(ungrouped_list[i:i+max_group_size])
    
    return refined_groups

def generate_group_er_diagram(schema, foreign_keys, group_tables, output_file, group_name):
    """Generate an ER diagram for a specific group of tables."""
    # Create a subgraph with only the tables in this group
    G = nx.DiGraph()
    
    # Add nodes (tables)
    for table in group_tables:
        if table in schema:
            info = schema[table]
            
            # Format table node label with columns
            label = f"{table}\n"
            label += "──────────\n"
            
            for col in info['columns']:
                pk_marker = "🔑 " if col['name'] in info['primary_keys'] else ""
                null_marker = "NOT NULL" if col['not_null'] else ""
                label += f"{pk_marker}{col['name']} ({col['type']}) {null_marker}\n"
            
            G.add_node(table, label=label)
    
    # Add edges (foreign keys) - but only for tables in this group
    for table in group_tables:
        if table in foreign_keys:
            for fk in foreign_keys[table]:
                ref_table = fk['to_table']
                if ref_table in group_tables:  # Only include if the referenced table is in this group
                    G.add_edge(
                        table, 
                        ref_table,
                        from_col=fk['from_col'],
                        to_col=fk['to_col']
                    )
    
    # Don't create empty diagrams
    if len(G.nodes) == 0:
        return False
    
    # Create the plot
    plt.figure(figsize=(16, 12))
    
    # Choose layout based on group size
    if len(G.nodes) <= 5:
        pos = nx.spring_layout(G, k=1.5, seed=42)
    elif len(G.nodes) <= 15:
        pos = nx.kamada_kawai_layout(G)
    else:
        try:
            import pydot
            pos = nx.nx_pydot.graphviz_layout(G, prog="dot")
        except (ImportError, Exception):
            pos = nx.spring_layout(G, k=2.0, iterations=100, seed=42)
    
    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=5000, node_color="lightblue", alpha=0.8)
    
    # Draw edges
    for edge in G.edges(data=True):
        source, target, data = edge
        source_pos = pos[source]
        target_pos = pos[target]
        
        arrow = FancyArrowPatch(
            source_pos, target_pos,
            connectionstyle="arc3,rad=0.1",
            arrowstyle="-|>",
            mutation_scale=20,
            lw=2,
            color="gray"
        )
        plt.gca().add_patch(arrow)
        
        # Add relationship label
        edge_label = f"{data.get('from_col')} → {data.get('to_col')}"
        edge_x = (source_pos[0] + target_pos[0]) / 2
        edge_y = (source_pos[1] + target_pos[1]) / 2
        plt.text(edge_x, edge_y, edge_label, fontsize=8, 
                 bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
    
    # Add table labels with columns
    for node, (x, y) in pos.items():
        plt.text(
            x, y, G.nodes[node]['label'],
            bbox=dict(facecolor='white', alpha=0.7, edgecolor='lightblue', boxstyle='round,pad=0.5'),
            ha='center', va='center', fontsize=8
        )
    
    plt.axis('off')
    plt.title(f"Entity-Relationship Diagram: {group_name}")
    
    try:
        plt.savefig(output_file, bbox_inches='tight', dpi=200)
        print(f"ER diagram saved to {output_file}")
        plt.close()
        return True
    except Exception as e:
        print(f"Error saving diagram: {e}")
        plt.close()
        return False

def generate_overview_diagram(schema, foreign_keys, output_file):
    """Generate a simplified overview ER diagram showing connections between tables."""
    G = nx.DiGraph()
    
    # Add nodes (tables) - simplified without column details
    for table in schema.keys():
        G.add_node(table)
    
    # Add edges (foreign keys)
    for table, fks in foreign_keys.items():
        for fk in fks:
            ref_table = fk['to_table']
            if ref_table in schema:  # Make sure the reference exists
                G.add_edge(table, ref_table)
    
    # Create the plot
    plt.figure(figsize=(16, 12))
    
    # Use a layout that spreads things out
    try:
        import pydot
        pos = nx.nx_pydot.graphviz_layout(G, prog="twopi")
    except (ImportError, Exception):
        pos = nx.spring_layout(G, k=2.0, iterations=200, seed=42)
    
    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=1500, node_color="lightblue", alpha=0.8)
    
    # Draw node labels (table names)
    nx.draw_networkx_labels(G, pos, font_size=8)
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, arrowsize=15, width=1.0, alpha=0.6, edge_color="gray")
    
    plt.title("Database Overview Diagram (Tables and Relationships)")
    plt.axis('off')
    
    try:
        plt.savefig(output_file, bbox_inches='tight', dpi=200)
        print(f"Overview diagram saved to {output_file}")
        plt.close()
        return True
    except Exception as e:
        print(f"Error saving overview diagram: {e}")
        plt.close()
        return False

def generate_table_list_file(schema, output_dir):
    """Generate a text file with all table names for reference."""
    output_file = os.path.join(output_dir, "table_list.txt")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("Database Tables\n")
            f.write("===============\n\n")
            for i, table in enumerate(sorted(schema.keys()), 1):
                column_count = len(schema[table]['columns'])
                f.write(f"{i}. {table} ({column_count} columns)\n")
        print(f"Table list saved to {output_file}")
        return True
    except Exception as e:
        print(f"Error saving table list: {e}")
        return False

def generate_html_index(schema, groups, output_dir):
    """Generate an HTML index page linking to all diagrams."""
    output_file = os.path.join(output_dir, "index.html")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("<!DOCTYPE html>\n")
            f.write("<html lang='en'>\n")
            f.write("<head>\n")
            f.write("    <meta charset='UTF-8'>\n")
            f.write("    <meta name='viewport' content='width=device-width, initial-scale=1.0'>\n")
            f.write("    <title>Database ER Diagrams</title>\n")
            f.write("    <style>\n")
            f.write("        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }\n")
            f.write("        h1, h2 { color: #333; }\n")
            f.write("        ul { list-style-type: none; padding: 0; }\n")
            f.write("        li { margin-bottom: 10px; }\n")
            f.write("        a { color: #0066cc; text-decoration: none; }\n")
            f.write("        a:hover { text-decoration: underline; }\n")
            f.write("        .container { max-width: 1200px; margin: 0 auto; }\n")
            f.write("        .diagram-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }\n")
            f.write("        .diagram-card { border: 1px solid #ddd; border-radius: 5px; padding: 15px; }\n")
            f.write("        .tables-section { margin-top: 40px; }\n")
            f.write("        .tables-list { column-count: 3; column-gap: 20px; }\n")
            f.write("        @media (max-width: 768px) { .tables-list { column-count: 1; } }\n")
            f.write("    </style>\n")
            f.write("</head>\n")
            f.write("<body>\n")
            f.write("    <div class='container'>\n")
            f.write("        <h1>Database ER Diagrams</h1>\n")
            
            # Overview diagram
            f.write("        <h2>Database Overview</h2>\n")
            f.write("        <p><a href='overview_diagram.png' target='_blank'>View complete database overview diagram</a></p>\n")
            
            # Group diagrams
            f.write("        <h2>Detailed Diagrams by Table Groups</h2>\n")
            f.write("        <div class='diagram-list'>\n")
            
            for i, group in enumerate(groups):
                if len(group) > 0:
                    group_name = f"Group {i+1}"
                    file_name = f"group_{i+1}_er.png"
                    
                    f.write("            <div class='diagram-card'>\n")
                    f.write(f"                <h3>{group_name}</h3>\n")
                    f.write(f"                <p><a href='{file_name}' target='_blank'>View diagram</a></p>\n")
                    f.write("                <h4>Tables in this group:</h4>\n")
                    f.write("                <ul>\n")
                    for table in sorted(group):
                        f.write(f"                    <li>{table}</li>\n")
                    f.write("                </ul>\n")
                    f.write("            </div>\n")
            
            f.write("        </div>\n")
            
            # All tables
            f.write("        <div class='tables-section'>\n")
            f.write("            <h2>Complete Table List</h2>\n")
            f.write("            <div class='tables-list'>\n")
            f.write("                <ul>\n")
            
            for table in sorted(schema.keys()):
                column_count = len(schema[table]['columns'])
                f.write(f"                    <li><strong>{table}</strong> ({column_count} columns)</li>\n")
            
            f.write("                </ul>\n")
            f.write("            </div>\n")
            f.write("        </div>\n")
            
            f.write("    </div>\n")
            f.write("</body>\n")
            f.write("</html>\n")
        
        print(f"HTML index page saved to {output_file}")
        return True
    
    except Exception as e:
        print(f"Error generating HTML index: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Generate focused ER diagrams for large databases")
    parser.add_argument("-p", "--path", default=".", help="Root path to search for the database")
    parser.add_argument("-o", "--output-dir", default="er_diagrams", help="Output directory for generated diagrams")
    parser.add_argument("-r", "--non-recursive", action="store_true", help="Don't search subdirectories")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Find the database
    print(f"Searching for inventory database in {args.path}...")
    db_path = find_inventory_database(args.path, not args.non_recursive)
    
    if not db_path:
        print("No inventory database found. Please check the path.")
        return
    
    print(f"Found database: {db_path}")
    
    # Create output directory if it doesn't exist
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    # Get database schema
    schema, foreign_keys = get_database_schema(db_path)
    if not schema or not foreign_keys:
        print(f"Failed to extract schema from {db_path}")
        return
    
    table_count = len(schema)
    print(f"Found {table_count} tables in the database")
    
    # Generate a simple list of all tables
    generate_table_list_file(schema, args.output_dir)
    
    # Generate an overview diagram (tables only, no columns)
    overview_file = os.path.join(args.output_dir, "overview_diagram.png")
    generate_overview_diagram(schema, foreign_keys, overview_file)
    
    # Group tables into logical subsets for more readable diagrams
    print("Identifying table groups for focused diagrams...")
    table_groups = identify_table_groups(schema, foreign_keys)
    
    # Generate diagrams for each group
    print(f"Generating {len(table_groups)} focused ER diagrams...")
    for i, group in enumerate(table_groups):
        group_name = f"Group {i+1}"
        output_file = os.path.join(args.output_dir, f"group_{i+1}_er.png")
        
        print(f"Generating diagram for {group_name} ({len(group)} tables)")
        generate_group_er_diagram(schema, foreign_keys, group, output_file, group_name)
    
    # Generate HTML index
    generate_html_index(schema, table_groups, args.output_dir)
    
    print(f"\nComplete! All diagrams have been saved to the '{args.output_dir}' directory.")
    print(f"Open '{os.path.join(args.output_dir, 'index.html')}' in your browser to view all diagrams.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation canceled by user.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)