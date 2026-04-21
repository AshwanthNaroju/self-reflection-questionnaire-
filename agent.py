import csv

def load_tree(file_path):
    nodes = {}
    children = {}

    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')

        for row in reader:
            node_id = row['id'].strip()
            parent = row['parent'].strip()

            nodes[node_id] = row

            if parent:
                children.setdefault(parent, []).append(node_id)

    return nodes, children


def run():
    nodes, children = load_tree("tree.tsv")

    score = 0

    root_nodes = [nid for nid, n in nodes.items() if n['parent'] == ""]

    for start in root_nodes:
        current = start

        while True:
            node = nodes[current]
            node_type = node['type'].strip()

            if node_type == 'question':
                print("\n" + node['text'])

                options = node['options'].split("|")
                for i, opt in enumerate(options, 1):
                    print(f"{i}. {opt}")

                try:
                    choice = int(input("Choose option: "))
                    answer = options[choice - 1]
                except:
                    print("Invalid input. Try again.")
                    continue

                if current not in children:
                    break

                next_node = children[current][0]
                next_type = nodes[next_node]['type'].strip()

                if next_type == 'reflection':
                    current = next_node
                    continue

                decision = nodes[next_node]
                mappings = decision['mapping'].split(";")

                matched = False
                for m in mappings:
                    if ":" not in m:
                        continue

                    key, value = m.split(":")
                    key = key.replace("answer=", "").strip()

                    if key == answer:
                        current = value.strip()
                        matched = True
                        break

                if not matched:
                    print("No valid path found.")
                    break

            elif node_type == 'reflection':
                print("\n🔍 Reflection:")
                print(node['text'])

                if node['score']:
                    try:
                        score += int(node['score'].replace("+", ""))
                    except:
                        pass
                break

            else:
                print("Invalid node type:", node_type)
                break

    print("\n📊 FINAL RESULT")
    
    if score >= 5:
        print("🌟 Mindset: Strong & Growth-Oriented")
    elif score >= 3:
        print("⚖️ Mindset: Balanced but Needs Improvement")
    else:
        print("🔧 Mindset: Needs Focus & Development")


if __name__ == "__main__":
    run()