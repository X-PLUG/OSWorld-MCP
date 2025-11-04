import os
import json
import re

def load_task_classification(no_tools_path, has_tools_path):
    with open(no_tools_path, 'r', encoding='utf-8') as f:
        no_tools = json.load(f)
    with open(has_tools_path, 'r', encoding='utf-8') as f:
        has_tools = json.load(f)
    return no_tools, has_tools

def count_total_tasks(task_dict):
    return sum(len(v) for v in task_dict.values())

def check_task_has_tool(traj_file, tool_list, sub_result):
    if not os.path.exists(traj_file):
        return False
    with open(traj_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            try:
                record = json.loads(line)
            except:
                continue
            if "prediction" in record:
                pred = record["prediction"]
                if not isinstance(pred, str):
                    continue
                match = re.search(r'<tool_call>\n\{"name": "(.+?)", "arguments"', pred)
                if match:
                    tool_name = match.group(1)
                    if tool_name != "computer_use" and tool_name in tool_list:
                        return True

                match = re.search(r'OsworldMcpClient.call_tool\(name=\'(.+)\', params=.+\);', pred)
                if match:
                    tool_name = match.group(1)
                    if tool_name != "computer_use" and tool_name in tool_list:
                        return True
                    
            if sub_result and i == 15:
                break
            
    return False

def check_result_success(task_dir, sub_result):

    result_file = os.path.join(task_dir, "result.txt")
    if sub_result and os.path.exists(os.path.join(task_dir, "result_15.txt")):
        result_file = os.path.join(task_dir, "result_15.txt")
    if not os.path.exists(result_file):
        return False
    with open(result_file, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        return "1" in content
    return False

def count_tools(base_path, no_tools, has_tools, tool_list, sub_result=False):
    no_tool_count = 0
    has_tool_count = 0

    for app_name in os.listdir(base_path):
        app_dir = os.path.join(base_path, app_name)
        if not os.path.isdir(app_dir):
            continue
        
        for task_name in os.listdir(app_dir):
            task_dir = os.path.join(app_dir, task_name)
            if not os.path.isdir(task_dir):
                continue

            traj_file = os.path.join(task_dir, "traj.jsonl")
            has_tool_flag = check_task_has_tool(traj_file, tool_list, sub_result)
            success_flag = check_result_success(task_dir, sub_result)

            if task_name in no_tools.get(app_name, []):
                if (not has_tool_flag) and success_flag:
                    no_tool_count += 1
            if task_name in has_tools.get(app_name, []):
                if has_tool_flag and success_flag:
                    has_tool_count += 1

    return no_tool_count, has_tool_count

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="统计 no_tools / has_tools 任务调用比例（带 result.txt 判断）")
    parser.add_argument("--base_path", required=True, help="任务数据根目录")
    parser.add_argument("--no_tools_path", required=True, help="no_tools.json 文件路径")
    parser.add_argument("--has_tools_path", required=True, help="has_tools.json 文件路径")
    parser.add_argument("--tool_list_path", required=False, help="工具列表txt文件路径，每行一个工具名")
    parser.add_argument('--sub_result', action='store_true')
    args = parser.parse_args()

    if args.tool_list_path:
        with open(args.tool_list_path, 'r', encoding='utf-8') as f:
            tool_list = set(line.strip() for line in f if line.strip())
    else:
        # 默认示例，实际用可替换为完整工具列表
        tool_list = set("""
osworld_mcp_code.add_folder
osworld_mcp_code.compare_files
osworld_mcp_code.disable_extension
osworld_mcp_code.goto_file
osworld_mcp_code.install_extension
osworld_mcp_code.launch_vscode
osworld_mcp_code.list_extensions
osworld_mcp_code.remove_folder
osworld_mcp_code.toggle_sync
osworld_mcp_code.uninstall_extension
osworld_mcp_code.update_extensions
osworld_mcp_code_ours.add_files_exclude
osworld_mcp_code_ours.replace_text
osworld_mcp_code_ours.search_text
osworld_mcp_code_ours.set_auto_save_delay
osworld_mcp_code_ours.set_color_theme
osworld_mcp_code_ours.set_focus_editor_on_break
osworld_mcp_code_ours.set_python_diagnostics_override
osworld_mcp_code_ours.set_word_wrap_column
osworld_mcp_code_ours.set_wrap_tabs
osworld_mcp_google_chrome.bookmark_page
osworld_mcp_google_chrome.bring_back_last_tab
osworld_mcp_google_chrome.chrome_open_tabs_setup
osworld_mcp_google_chrome.delete_browsing_data
osworld_mcp_google_chrome.open_appearance_settings
osworld_mcp_google_chrome.open_bookmarks
osworld_mcp_google_chrome.open_extensions
osworld_mcp_google_chrome.open_password_settings
osworld_mcp_google_chrome.open_privacy_settings
osworld_mcp_google_chrome.open_profile_settings
osworld_mcp_google_chrome.open_search_engine_settings
osworld_mcp_google_chrome.print
osworld_mcp_libreoffice_calc.adjust_column_width
osworld_mcp_libreoffice_calc.adjust_row_height
osworld_mcp_libreoffice_calc.copy_sheet
osworld_mcp_libreoffice_calc.create_chart
osworld_mcp_libreoffice_calc.create_pivot_table
osworld_mcp_libreoffice_calc.env_info
osworld_mcp_libreoffice_calc.export_to_csv
osworld_mcp_libreoffice_calc.export_to_pdf
osworld_mcp_libreoffice_calc.format_range
osworld_mcp_libreoffice_calc.freeze_panes
osworld_mcp_libreoffice_calc.get_column_data
osworld_mcp_libreoffice_calc.get_workbook_info
osworld_mcp_libreoffice_calc.hide_row_data
osworld_mcp_libreoffice_calc.highlight_range
osworld_mcp_libreoffice_calc.merge_cells
osworld_mcp_libreoffice_calc.rename_sheet
osworld_mcp_libreoffice_calc.reorder_columns
osworld_mcp_libreoffice_calc.reorder_sheets
osworld_mcp_libreoffice_calc.save
osworld_mcp_libreoffice_calc.set_cell_value
osworld_mcp_libreoffice_calc.set_column_values
osworld_mcp_libreoffice_calc.set_number_format
osworld_mcp_libreoffice_calc.set_zoom_level
osworld_mcp_libreoffice_calc.sort_column
osworld_mcp_libreoffice_calc.switch_active_sheet
osworld_mcp_libreoffice_calc.transpose_range
osworld_mcp_libreoffice_calc_ours.copy_cells_between_sheets
osworld_mcp_libreoffice_calc_ours.fill_blank_down
osworld_mcp_libreoffice_calc_ours.format_numbers_to_human_readable
osworld_mcp_libreoffice_calc_ours.scale_first_sheet_and_export_pdf
osworld_mcp_libreoffice_writer.save
osworld_mcp_libreoffice_writer.write_text
osworld_mcp_libreoffice_writer.set_color
osworld_mcp_libreoffice_writer.find_and_replace
osworld_mcp_libreoffice_writer.set_font
osworld_mcp_libreoffice_writer.set_line_spacing
osworld_mcp_libreoffice_writer.insert_formula_at_cursor
osworld_mcp_libreoffice_writer.insert_image_at_cursor
osworld_mcp_libreoffice_writer.set_font_size
osworld_mcp_libreoffice_writer.export_to_pdf
osworld_mcp_libreoffice_writer.set_paragraph_alignment
osworld_mcp_libreoffice_writer.set_default_font
osworld_mcp_libreoffice_writer.add_page_numbers
osworld_mcp_libreoffice_writer.insert_page_break
osworld_mcp_libreoffice_writer.env_info
osworld_mcp_libreoffice_impress.configure_auto_save
osworld_mcp_libreoffice_impress.delete_content
osworld_mcp_libreoffice_impress.duplicate_slide
osworld_mcp_libreoffice_impress.env_info
osworld_mcp_libreoffice_impress.export_to_image
osworld_mcp_libreoffice_impress.get_slide_count
osworld_mcp_libreoffice_impress.go_to_slide
osworld_mcp_libreoffice_impress.insert_file
osworld_mcp_libreoffice_impress.insert_image
osworld_mcp_libreoffice_impress.position_box
osworld_mcp_libreoffice_impress.save
osworld_mcp_libreoffice_impress.save_as
osworld_mcp_libreoffice_impress.set_background_color
osworld_mcp_libreoffice_impress.set_slide_background
osworld_mcp_libreoffice_impress.set_slide_font
osworld_mcp_libreoffice_impress.set_slide_orientation
osworld_mcp_libreoffice_impress.set_style
osworld_mcp_libreoffice_impress.set_text_color
osworld_mcp_libreoffice_impress.set_text_strikethrough
osworld_mcp_libreoffice_impress.set_textbox_alignment
osworld_mcp_libreoffice_impress.write_text
osworld_mcp_libreoffice_impress_ours.convert_to_docx
osworld_mcp_os_ours.change_text_scale
osworld_mcp_os_ours.configure_auto_lock
osworld_mcp_os_ours.copy_matching_files_with_hierarchy
osworld_mcp_os_ours.get_do_not_disturb_status
osworld_mcp_os_ours.get_text_scale
osworld_mcp_os_ours.get_trash_directory
osworld_mcp_os_ours.get_volume
osworld_mcp_os_ours.open_shell
osworld_mcp_os_ours.rename_directory
osworld_mcp_os_ours.restore_file
osworld_mcp_os_ours.search_files
osworld_mcp_os_ours.set_default_terminal_size
osworld_mcp_os_ours.set_do_not_disturb
osworld_mcp_os_ours.set_volume
osworld_mcp_os_ours_2.convert_image_format
osworld_mcp_os_ours_2.ffmpeg_video_to_gif
osworld_mcp_os_ours_2.git_operation
osworld_mcp_os_ours_2.git_set_user_info
osworld_mcp_os_ours_2.remove_image_background
osworld_mcp_test.calculator_add
osworld_mcp_vlc.add_to_playlist
osworld_mcp_vlc.get_current_time
osworld_mcp_vlc.get_media_duration
osworld_mcp_vlc.get_media_files
osworld_mcp_vlc.get_playlist
osworld_mcp_vlc.get_settings
osworld_mcp_vlc.next
osworld_mcp_vlc.pause
osworld_mcp_vlc.play
osworld_mcp_vlc.previous
osworld_mcp_vlc.set_settings
osworld_mcp_vlc.toggle_fullscreen
filesystem_read_file
filesystem_read_text_file
filesystem_read_media_file
filesystem_read_multiple_files
filesystem_write_file
filesystem_edit_file
filesystem_create_directory
filesystem_list_directory
filesystem_list_directory_with_sizes
filesystem_directory_tree
filesystem_move_file
filesystem_search_files
filesystem_get_file_info
filesystem_list_allowed_directories
git_git_status
git_git_diff_unstaged
git_git_diff_staged
git_git_diff
git_git_commit
git_git_add
git_git_reset
git_git_log
git_git_create_branch
git_git_checkout
git_git_show
git_git_init
git_git_branch
""".strip().split("\n"))

    # 加载任务分类
    no_tools, has_tools = load_task_classification(args.no_tools_path, args.has_tools_path)

    # 总任务数
    no_tools_total = count_total_tasks(no_tools)
    has_tools_total = count_total_tasks(has_tools)
    total_tasks = no_tools_total + has_tools_total

    # 符合条件的任务数
    no_tool_count, has_tool_count = count_tools(args.base_path, no_tools, has_tools, tool_list, args.sub_result)
    finished_tasks = no_tool_count + has_tool_count

    # 计算比例
    completion_rate = finished_tasks / total_tasks if total_tasks > 0 else 0
    no_tool_rate = no_tool_count / no_tools_total if no_tools_total > 0 else 0
    has_tool_rate = has_tool_count / has_tools_total if has_tools_total > 0 else 0

    result = {
        "all_rate": round(completion_rate, 4),
        "no_tool_rate": round(no_tool_rate, 4),
        "has_tool_rate": round(has_tool_rate, 4)
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))
