import sqlite3
import argparse
import os
import glob
from pathlib import Path
import logging
import sys

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

def generate_er_diagram(schema, foreign_keys, output_file=None):
    """Generate an ER diagram using NetworkX and Matplotlib."""
    G = nx.DiGraph()
    
    # Add nodes (tables)
    for table, info in schema.items():
        # Format table node label with columns, handling Unicode safely
        label = f"{table}\n"
        label += "──────────\n"
        
        for col in info['columns']:
            pk_marker = "PK " if col['name'] in info['primary_keys'] else ""
            null_marker = "NOT NULL" if col['not_null'] else ""
            label += f"{pk_marker}{col['name']} ({col['type']}) {null_marker}\n"
        
        G.add_node(table, label=label)
    
    # Add edges (foreign keys)
    for table, fks in foreign_keys.items():
        for fk in fks:
            G.add_edge(
                table, 
                fk['to_table'],
                from_col=fk['from_col'],
                to_col=fk['to_col']
            )
    
    # Create the plot
    plt.figure(figsize=(14, 12))
    
    # Use different layout algorithms based on graph size
    if len(G.nodes) <= 5:
        pos = nx.spring_layout(G, k=1.5)
    elif len(G.nodes) <= 15:
        pos = nx.kamada_kawai_layout(G)
    else:
        try:
            # Try to use graphviz if available
            import pydot
            pos = nx.nx_pydot.graphviz_layout(G, prog="dot")
        except (ImportError, Exception):
            # Fall back to spring layout
            pos = nx.spring_layout(G, k=2.0, iterations=100)
    
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
        
        # Add relationship label, handling Unicode safely
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
    plt.title("Entity-Relationship Diagram")
    
    if output_file:
        # Fix encoding issues by using a safe name
        try:
            plt.savefig(output_file, bbox_inches='tight', dpi=150)
            print(f"ER diagram saved to {output_file}")
            return True
        except Exception as e:
            print(f"Error saving diagram: {e}")
            # Try with a simpler filename if the original fails
            simple_path = os.path.join(os.path.dirname(output_file), "inventory_er_diagram.png")
            try:
                plt.savefig(simple_path, bbox_inches='tight', dpi=150)
                print(f"ER diagram saved to {simple_path}")
                return True
            except Exception as e2:
                print(f"Error saving with simple filename: {e2}")
                return False
    else:
        plt.show()
        return True

def generate_mermaid_diagram(schema, foreign_keys, output_file=None):
    """Generate a Mermaid.js ER diagram code."""
    mermaid_code = "```mermaid\nerDiagram\n"
    
    # Add entities and their attributes
    for table, info in schema.items():
        table_safe = table.replace('-', '_').replace(' ', '_')  # Safe table name for Mermaid
        mermaid_code += f"    {table_safe} {{\n"
        
        for col in info['columns']:
            pk_marker = "PK " if col['name'] in info['primary_keys'] else ""
            type_str = col['type'] if col['type'] else "TEXT"
            
            # Handle potential Unicode issues by escaping or replacing problematic characters
            col_name_safe = col['name'].replace('-', '_').replace(' ', '_')
            type_str_safe = type_str.replace('"', '').replace("'", "")
            
            mermaid_code += f"        {type_str_safe} {col_name_safe} {pk_marker}\n"
        
        mermaid_code += "    }\n"
    
    # Add relationships
    for table, fks in foreign_keys.items():
        table_safe = table.replace('-', '_').replace(' ', '_')
        for fk in fks:
            to_table_safe = fk['to_table'].replace('-', '_').replace(' ', '_')
            from_col_safe = fk['from_col'].replace('-', '_').replace(' ', '_')
            to_col_safe = fk['to_col'].replace('-', '_').replace(' ', '_')
            
            relation = f"    {table_safe} ||--o{{ {to_table_safe} : \"{from_col_safe} -> {to_col_safe}\"\n"
            mermaid_code += relation
    
    mermaid_code += "```\n"
    
    if output_file:
        try:
            # Write using UTF-8 encoding to handle special characters
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(mermaid_code)
            print(f"Mermaid diagram code saved to {output_file}")
            return True
        except Exception as e:
            print(f"Error saving Mermaid diagram: {e}")
            # Try with a simpler filename
            simple_path = os.path.join(os.path.dirname(output_file), "inventory_er_diagram.md")
            try:
                with open(simple_path, 'w', encoding='utf-8') as f:
                    f.write(mermaid_code)
                print(f"Mermaid diagram code saved to {simple_path}")
                return True
            except Exception as e2:
                print(f"Error saving with simple filename: {e2}")
                return False
    else:
        print("\nMermaid.js ER Diagram Code:")
        print(mermaid_code)
        return True

def main():
    parser = argparse.ArgumentParser(description="Automatically generate ER diagram for inventory database")
    parser.add_argument("-p", "--path", default=".", help="Root path to search for the inventory database")
    parser.add_argument("-o", "--output-dir", default="er_diagrams", help="Output directory for generated diagrams")
    parser.add_argument("-m", "--mermaid", action="store_true", help="Generate Mermaid.js diagram instead of visual one")
    parser.add_argument("-r", "--non-recursive", action="store_true", help="Don't search subdirectories")
    
    args = parser.parse_args()
    
    # Setup logging with encoding handling
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Set console encoding to handle Unicode
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    
    # Find the inventory database
    print(f"Searching for inventory database in {args.path}...")
    db_path = find_inventory_database(args.path, not args.non_recursive)
    
    if not db_path:
        print("No inventory database found. Please check the path.")
        return
    
    print(f"Found inventory database: {db_path}")
    
    # Create output directory if it doesn't exist
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    # Get schema and generate diagram
    schema, foreign_keys = get_database_schema(db_path)
    if not schema or not foreign_keys:
        print(f"Failed to extract schema from {db_path}")
        return
    
    table_count = len(schema)
    print(f"Found {table_count} tables in the database")
    
    # Get safe base filename 
    db_name = os.path.basename(db_path)
    base_name = os.path.splitext(db_name)[0]
    safe_name = "inventory_database"  # Use a simple, safe name
    
    # Generate diagram(s)
    if args.mermaid:
        mermaid_file = os.path.join(args.output_dir, f"{safe_name}_er.md")
        success = generate_mermaid_diagram(schema, foreign_keys, mermaid_file)
    else:
        diagram_file = os.path.join(args.output_dir, f"{safe_name}_er.png")
        success = generate_er_diagram(schema, foreign_keys, diagram_file)
    
    if success:
        print("ER diagram generation completed successfully.")
    else:
        print("Failed to generate ER diagram.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation canceled by user.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)