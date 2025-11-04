import os
import json

def get_result(target_dir, meta_path, sub_result):
    all_result = []
    domain_result = {}
    all_result_for_analysis = {}

    with open(meta_path, 'r') as f:
        meta = json.load(f)

    num_tasks = 0
    for tasks in meta.values():
        num_tasks += len(tasks)

    for domain in os.listdir(target_dir):
        domain_path = os.path.join(target_dir, domain)
        if os.path.isdir(domain_path):
            for example_id in os.listdir(domain_path):
                example_path = os.path.join(domain_path, example_id)
                if example_id not in meta[domain]:
                    continue
                
                if os.path.isdir(example_path):
                    if "result.txt" in os.listdir(example_path):
                        if domain not in domain_result:
                            domain_result[domain] = []

                        result = open(os.path.join(example_path, "result.txt"), "r").read()
                        if sub_result and "result_15.txt" in os.listdir(example_path):
                            result = open(os.path.join(example_path, "result_15.txt"), "r").read()

                        try:
                            domain_result[domain].append(float(result))
                        except:
                            domain_result[domain].append(float(eval(result)))

                        if domain not in all_result_for_analysis:
                            all_result_for_analysis[domain] = {}
                        all_result_for_analysis[domain][example_id] = domain_result[domain][-1]

                        try:
                            result = open(os.path.join(example_path, "result.txt"), "r").read()
                            if sub_result and "result_15.txt" in os.listdir(example_path):
                                result = open(os.path.join(example_path, "result_15.txt"), "r").read()
                            try:
                                all_result.append(float(result))
                            except:
                                all_result.append(float(bool(result)))
                        except:
                            all_result.append(0.0)

    print(f"Run: {len(all_result)}/{num_tasks}", "Mean acc: ", sum(all_result) / len(all_result))
    return all_result


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--root_path', type=str, default='')
    parser.add_argument('--meta_path', type=str, default='')
    parser.add_argument('--sub_result', action='store_true')

    args = parser.parse_args()

    get_result(args.root_path, args.meta_path, args.sub_result)