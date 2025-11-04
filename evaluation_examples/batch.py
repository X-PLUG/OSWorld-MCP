import json
import subprocess
import numpy as np

def average_arrays_with_empty(arrays):

    processed = []
    for arr in arrays:
        processed.append([
            float(x) if x != '' else None
            for x in arr
        ])

    arr_np = np.array(processed, dtype=object)
    mean_result = []

    for col in arr_np.T:  
        valid_nums = [x for x in col if x is not None]
        if valid_nums:
            mean_val = round(np.mean(valid_nums), 1)
            mean_result.append(mean_val)
        else:
            mean_result.append('-')  
    return mean_result


def format_mean_array(mean_array):
    
    return ''.join((str(num) if num != '-' else '-') + ' & ' for num in mean_array)


def compare_means(mean1, mean2):
    res = ''
    for v1, v2 in zip(mean1, mean2):
        if v1 == '-':
            
            res += (str(v2) if v2 != '-' else '-') + ' & '
        else:
            diff = round(v2 - v1, 1)
            if diff > 0:
                res += f"{v2}$_{{\\;{diff}\\uparrow}}$ & "
            elif diff < 0:
                res += f"{v2}$_{{\\;{abs(diff)}\\downarrow}}$ & "
            else:
                res += f"{v2} & "
    return res

def run_and_parse(seed_path, sub_result=False):
    
    HAS_TOOL_JSON = "has_tool.json"
    NO_TOOL_JSON = "task_with_0_tools.json"
    ALL_JSON = "test_all.json"
    TOOL_LIST = "tool_list.txt"

    def get_metrics(meta_path):
        
        params = []
        if sub_result:
            params = ['--sub_result']
        pass_out = subprocess.check_output([
            "python", "show_result.py",
            f"--root_path={seed_path}",
            f"--meta_path={meta_path}",
        ] + params, text=True)
        print(pass_out.strip())
        acc_line = [l for l in pass_out.splitlines() if "Mean acc" in l][-1]
        acc = float(acc_line.split(":")[-1].strip())

        count_out = subprocess.check_output([
            "python", "count_tools.py",
            "--base_path", seed_path,
            "--no_tools_path", NO_TOOL_JSON,
            "--has_tools_path", meta_path,
            "--tool_list_path", TOOL_LIST
        ] + params, text=True)

        json_str = count_out[count_out.find("{"):count_out.rfind("}") + 1]
        metrics_dict = json.loads(json_str)
        all_rate = float(metrics_dict["all_rate"])
        no_tool_rate = float(metrics_dict["no_tool_rate"])
        has_tool_rate = float(metrics_dict["has_tool_rate"])

        step_out = subprocess.check_output([
            "python", "collect_steps.py",
            "--base_path", seed_path,
            "--has_tools_json", meta_path
        ] + params, text=True)
        step_line = [l for l in step_out.splitlines() if "任务的平均完成步数值" in l][-1]
        step = float(step_line.split(":")[-1].strip())

        return acc, all_rate, no_tool_rate, has_tool_rate, step

    has_acc, has_all_rate, has_no_tool_rate, has_has_tool_rate, has_step = get_metrics(HAS_TOOL_JSON)
    no_acc, _, _, _, no_step = get_metrics(NO_TOOL_JSON)
    all_acc, _, _, _, all_step = get_metrics(ALL_JSON)

    def fmt_acc_rate(x):
        
        return f"{x*100:.1f}"

    def fmt_step(x):
        
        return f"{x:.1f}"

    # 如果 seed_path1 含 gui，则 rate 留空
    hide_rate = "gui" in seed_path.lower()
    if hide_rate:
        rate_or_empty = lambda x: ""  # 占位，空字符串
    else:
        rate_or_empty = fmt_acc_rate

    return [
        fmt_acc_rate(has_acc),            # 1 has_tool acc
        rate_or_empty(has_has_tool_rate), # 2 has_tool_rate
        fmt_step(has_step),               # 3 has_step
        fmt_acc_rate(no_acc),             # 4 no_tool acc
        rate_or_empty(has_no_tool_rate),  # 5 has_tool.json no_tool_rate
        fmt_step(no_step),                # 6 no_tool step
        fmt_acc_rate(all_acc),            # 7 all acc
        rate_or_empty(has_all_rate),      # 8 has_tool all_rate
        fmt_step(all_step)                # 9 all step
    ]


if __name__ == "__main__":
    paths = [
            ]   
    paths15 = [
            ]

    paths50 = [
           ]
    arrays15 = []
    arrays50 = []
    for path in paths15:
        print('[exp]', path)

        print('===== 15 steps =====')
        a = run_and_parse(path, sub_result=True)
        print(a)
        a = np.array(a)
        arrays15.append(a)

    mean_array = average_arrays_with_empty(arrays15)
    res15 = ''
    for num in mean_array:
        res15 += str(num) + ' & '
    print('Average 15')
    print(res15)
    for path in paths50:
        print('[exp]', path)

        print('===== 50 steps =====')
        a = run_and_parse(path)
        print(a)
        a = np.array(a)
        arrays50.append(a)
    mean_array = average_arrays_with_empty(arrays50)
    res50 = ''
    for num in mean_array:
        res50 += str(num) + ' & '

    print('Average 50')
    print(res50)
