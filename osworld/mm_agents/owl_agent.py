import ast
import base64
import logging
import math
import re
import xml.etree.ElementTree as ET
from io import BytesIO
from typing import Dict, List
import os

import backoff
import numpy as np
from PIL import Image
from requests.exceptions import SSLError
import openai
from openai import OpenAI
from google.api_core.exceptions import (
    BadRequest,
    InternalServerError,
    InvalidArgument,
    ResourceExhausted,
)
import uuid
import json
from typing import Tuple, Optional
import json_repair
import requests
import random
import io

from mm_agents.accessibility_tree_wrap.heuristic_retrieve import (
    filter_nodes,
)

from qwen_agent.llm.fncall_prompts.nous_fncall_prompt import (
    NousFnCallPrompt,
    Message,
    ContentItem,
)
from mm_agents.coordinate_resize import update_image_size_, convert_point_format
from mm_agents.agent_function_call import *

import dashscope

def remove_base64_images(messages):
    def is_base64_image(url):
        return bool(re.match(r'^data:image/.+;base64,', url))

    cleaned_messages = []

    for message in messages:
        if message["role"] == "user":
            cleaned_content = []
            for item in message["content"]:
                if 'type' in item:
                    if item["type"] == "text":
                        cleaned_content.append(item)  # Keep text content as it is
                    elif item["type"] == "image_url":
                        if not is_base64_image(item["image_url"]['url']):
                            cleaned_content.append(item)  # Keep non-base64 image URLs
                else:
                    # for dashscope-like output
                    if 'image' not in item:
                        cleaned_content.append(item)

            cleaned_message = {
                "role": message["role"],
                "content": cleaned_content
            }
            cleaned_messages.append(cleaned_message)
        else:
            cleaned_messages.append(message)

    return cleaned_messages


def get_prompt_new(
        width, height, instruction, history, use_dashscope=False, 
        tool_name='', tool_list=[], model='qwen2.5-vl-72b-instruct'):
    current_image_ele = update_image_size_({'image': "None", 'width': width, 'height': height})
    if "claude" in model:
        resized_width, resized_height = 1280, 720
    else:
        resized_width, resized_height = current_image_ele['resized_width'], current_image_ele['resized_height']
    computer_use = ComputerUse(
        cfg={"display_width_px": resized_width, "display_height_px": resized_height}
    )

    functions = [
        computer_use.function, 
    ]
    functions.extend(tool_list)

    system_message = NousFnCallPrompt().preprocess_fncall_messages(
        messages=[
            Message(role="system", content=[ContentItem(text="You are a helpful assistant.")]),
        ],
        functions=functions,
        lang=None,
    )
    system_message = system_message[0].model_dump()

    user_prompt = '''Please generate the next move according to the UI screenshot, instruction and previous actions.
    Instruction: {instruction}
    Previous actions:
    {history}
    Before answering, explain your reasoning step-by-step in <thinking></thinking> tags, and insert them before the <tool_call></tool_call> XML tags.\nAfter answering, summarize your action in <conclusion></conclusion> tags, and insert them after the <tool_call></tool_call> XML tags.'''
    if use_dashscope:
        messages=[
            {
                "role": "system",
                "content": [
                    {"text": msg["text"]} for msg in system_message["content"]
                ],
            },
            {
                "role": "user",
                "content": [
                    {"text": user_prompt.format(instruction=instruction, history=history)}
                ]
            }
        ]
    else:
        messages=[
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": msg["text"]} for msg in system_message["content"]
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt.format(instruction=instruction, history=history)}
                ]
            }
        ]
    return messages


logger = logging.getLogger("desktopenv.agent")

attributes_ns_ubuntu = "https://accessibility.windows.example.org/ns/attributes"
attributes_ns_windows = "https://accessibility.windows.example.org/ns/attributes"
state_ns_ubuntu = "https://accessibility.ubuntu.example.org/ns/state"
state_ns_windows = "https://accessibility.windows.example.org/ns/state"
component_ns_ubuntu = "https://accessibility.ubuntu.example.org/ns/component"
component_ns_windows = "https://accessibility.windows.example.org/ns/component"
value_ns_ubuntu = "https://accessibility.ubuntu.example.org/ns/value"
value_ns_windows = "https://accessibility.windows.example.org/ns/value"
class_ns_windows = "https://accessibility.windows.example.org/ns/class"
# More namespaces defined in OSWorld, please check desktop_env/server/main.py

def escape_single_quotes(text):
    # 匹配未转义的单引号（不匹配 \\'）
    pattern = r"(?<!\\)'"
    return re.sub(pattern, r"\\'", text)

def parse_action_fncall_id(text, image_path, height, width, model_name):
    thought = ""
    if "<thinking>" in text and "</thinking>" in text:
        thought = text.split("<thinking>")[-1].split("</thinking>")[0]
    elif "<thinking>" in text:
        thought = text.split("<thinking>")[1]

    conclusion = ""
    if "<conclusion>" in text and "</conclusion>" in text:
        conclusion = text.split("<conclusion>")[-1].split("</conclusion>")[0]
    elif "<conclusion>" in text:
        conclusion = text.split("<conclusion>")[1]
    if conclusion == "" and thought != "":
        conclusion = thought

    if "<tool_call>" in text and "</tool_call>" in text:
        action = text.split("<tool_call>")[-1].split("</tool_call>")[0]
    else:
        action = text.split("<tool_call>")[-1].split("<conclusion>")[0]
        action = action[:action.rfind('}') + 1]

    action_json = json.loads(action.strip('\n'))['arguments']

    if "computer_use" in action:
        current_image_ele = update_image_size_({'image': "None", 'width': width, 'height': height})

        if action_json['action'] == "key":
            action_type = 'hotkey'
            keys = action_json['keys']
            keys_str = ""
            for key in keys:
                keys_str += " " + key
            action_inputs = {"hotkey": keys_str}
        elif action_json['action'] == "type":
            action_type = "type"
            if 'clear' not in action_json:
                action_json['clear'] = 0
            if 'enter' not in action_json:
                action_json['enter'] = 0
            action_inputs = {'content': action_json['text'], 'clear': int(action_json['clear']), 'enter': int(action_json['enter'])}
        elif action_json['action'] == "mouse_move":
            action_type = "hover"
            x, y = convert_point_format([action_json['coordinate'][0], action_json['coordinate'][1]], current_image_ele, src_format='abs_resized', tgt_format='abs_origin', model_name=model_name)
            action_inputs = {'start_box': [x, y]}
        elif action_json['action'] == "left_click_drag" or action_json['action'] == "drag":
            action_type = "drag"
            x, y = convert_point_format([action_json['coordinate'][0], action_json['coordinate'][1]], current_image_ele, src_format='abs_resized', tgt_format='abs_origin', model_name=model_name)
            x2, y2 = convert_point_format([action_json['coordinate2'][0], action_json['coordinate2'][1]], current_image_ele, src_format='abs_resized', tgt_format='abs_origin', model_name=model_name)
            action_inputs = {'start_box': [x, y], 'end_box': [x2, y2]}
        elif action_json['action'] == "left_click" or action_json['action'] == "click":
            action_type = "click"
            x, y = convert_point_format([action_json['coordinate'][0], action_json['coordinate'][1]], current_image_ele, src_format='abs_resized', tgt_format='abs_origin', model_name=model_name)
            action_inputs = {'start_box': [x, y]}
        elif action_json['action'] == "right_click":
            action_type = "right_single"
            x, y = convert_point_format([action_json['coordinate'][0], action_json['coordinate'][1]], current_image_ele, src_format='abs_resized', tgt_format='abs_origin', model_name=model_name)
            action_inputs = {'start_box': [x, y]}
        elif action_json['action'] == "double_click":
            action_type = "left_double"
            x, y = convert_point_format([action_json['coordinate'][0], action_json['coordinate'][1]], current_image_ele, src_format='abs_resized', tgt_format='abs_origin', model_name=model_name)
            action_inputs = {'start_box': [x, y]}
        elif action_json['action'] == "scroll":
            action_type = "scroll"
            action_inputs = {'pixels': action_json['pixels']}
        elif action_json['action'] == "terminate":
            if action_json['status'] == 'success':
                action_type = "finished"
            else:
                action_type = "fail"
            action_inputs = {}
        elif action_json['action'] == "wait":
            action_type = "wait"
            action_inputs = {'time': action_json['time'] if 'time' in action_json else 1}

    else:
        # mcp tool call
        parsed_action = json.loads(action.strip('\n'))
        action_type = parsed_action['name']
        action_inputs = parsed_action['arguments']

    actions = []
    actions.append({
        "thought": thought,
        "conclusion": conclusion,
        "action_type": action_type,
        "action_inputs": action_inputs,
        "text": text
    })
    return actions



def parsing_response_to_pyautogui_code(responses, image_height: int, image_width:int, input_swap:bool=True) -> str:
    '''
    将M模型的输出解析为OSWorld中的action，生成pyautogui代码字符串
    参数:
        response: 包含模型输出的字典，结构类似于：
        {
            "action_type": "hotkey",
            "action_inputs": {
                "hotkey": "v ctrl",
                "start_box": None,
                "end_box": None
            }
        }
    返回:
        生成的pyautogui代码字符串
    '''

    pyautogui_code = f"import pyautogui\nimport time\n"
    if isinstance(responses, dict):
        responses = [responses]
    for response_id, response in enumerate(responses):
        if "observation" in response:
            observation = response["observation"]
        else:
            observation = ""

        if "thought" in response:
            thought = response["thought"]
        else:
            thought = ""
        
        if response_id == 0:
            pass
        else:
            pyautogui_code += f"\ntime.sleep(3)\n"

        action_dict = response
        action_type = action_dict.get("action_type")
        action_inputs = action_dict.get("action_inputs", {})
        
        if action_type == "hotkey":
            # Parsing hotkey action
            if "key" in action_inputs:
                hotkey = action_inputs.get("key", "")
            else:
                hotkey = action_inputs.get("hotkey", "")

            if hotkey:
                # Handle other hotkeys
                keys = hotkey.split()  # Split the keys by space
                pyautogui_code += f"\npyautogui.hotkey({', '.join([repr(k) for k in keys])})"
        
        elif action_type == "type":
            # Parsing typing action using clipboard
            content = action_inputs.get("content", "")
            content = escape_single_quotes(content)
            if content:
                if input_swap:
                    pyautogui_code += f"\nimport pyperclip"
                    pyautogui_code += f"\npyperclip.copy('{content.strip()}')"
                    pyautogui_code += f"\npyautogui.hotkey('ctrl', 'v')"
                    pyautogui_code += f"\ntime.sleep(0.5)\n"
                    if content.endswith("\n") or content.endswith("\\n"):
                        pyautogui_code += f"\npyautogui.press('enter')"
                else:
                    if action_inputs['clear']==1:
                        pyautogui_code += f"\npyautogui.hotkey('ctrl', 'a')"
                        pyautogui_code += f"\npyautogui.press('backspace')"
                    pyautogui_code += f"\npyautogui.write('{content.strip()}', interval=0.1)"
                    pyautogui_code += f"\ntime.sleep(0.5)\n"
                    if content.endswith("\n") or content.endswith("\\n") or action_inputs['enter']==1:
                        pyautogui_code += f"\npyautogui.press('enter')"

        elif action_type == "typed":
            # Parsing typing action using clipboard
            content = action_inputs.get("content", "")
            # content = escape_single_quotes(content)
            if content:
                if input_swap:
                    pyautogui_code += f"\npyautogui.hotkey('ctrl', 'alt', 't')"
                    pyautogui_code += f"\ntime.sleep(3)\n"
                    pyautogui_code += f"\nimport pyperclip"
                    pyautogui_code += f"\npyperclip.copy('{content.strip()}')"
                    pyautogui_code += f"\npyautogui.hotkey('ctrl', 'v')"
                    pyautogui_code += f"\ntime.sleep(0.5)\n"
                    if content.endswith("\n") or content.endswith("\\n"):
                        pyautogui_code += f"\npyautogui.press('enter')"
                else:
                    pyautogui_code += f"\npyautogui.hotkey('ctrl', 'alt', 't')"
                    pyautogui_code += f"\ntime.sleep(3)\n"
                    if action_inputs['clear'] == 1:
                        pyautogui_code += f"\npyautogui.hotkey('ctrl', 'a')"
                        pyautogui_code += f"\npyautogui.press('backspace')"
                    pyautogui_code += f"\npyautogui.write('{content.strip()}', interval=0.1)"
                    pyautogui_code += f"\ntime.sleep(0.5)\n"
                    if content.endswith("\n") or content.endswith("\\n") or action_inputs['enter'] == 1:
                        pyautogui_code += f"\npyautogui.press('enter')"
        elif action_type == "execute":
            content = action_inputs.get("content", "")
            # content = escape_single_quotes(content)
            if content:
                pyautogui_code += f"\n{content.strip()}"
        elif action_type == "OPEN_CHROME_TAB":
            content = action_inputs.get("content", "")
            # content = escape_single_quotes(content)
            if content:
                return f"OPEN_CHROME_TAB: {content.strip()}"

        
        elif action_type in ["drag", "select"]:
            # Parsing drag or select action based on start and end_boxes
            start_box = action_inputs.get("start_box")
            end_box = action_inputs.get("end_box")
            if start_box and end_box:
                sx, sy = start_box
                ex, ey = end_box
                pyautogui_code += (
                    f"\npyautogui.moveTo({sx}, {sy})\n"
                    f"\npyautogui.dragTo({ex}, {ey}, duration=1.0)\n"
                )

        elif action_type == "scroll":
            # Parsing scroll action
            start_box = action_inputs.get("start_box")
            if start_box:
                x1, y1, x2, y2 = eval(start_box)  # Assuming box is in [x1, y1, x2, y2]
                x = round(float((x1 + x2) / 2) * image_width, 3)
                y = round(float((y1 + y2) / 2) * image_height, 3)
            else:
                x = None
                y = None
            pixels = action_inputs.get("pixels")
            pyautogui_code += f"\npyautogui.scroll({pixels})"

        elif action_type in ["click", "left_single", "left_double", "right_single", "hover"]:
            # Parsing mouse click actions
            start_box = action_inputs.get("start_box")
            start_box = str(start_box)
            if start_box:
                start_box = eval(start_box)
                if len(start_box) == 4:
                    x1, y1, x2, y2 = start_box  # Assuming box is in [x1, y1, x2, y2]
                elif len(start_box) == 2:
                    x1, y1 = start_box
                    x2 = x1
                    y2 = y1
                    x = x1
                    y = y1

                if action_type == "left_single" or action_type == "click":
                    pyautogui_code += f"\npyautogui.click({x}, {y}, button='left')"
                elif action_type == "left_double":
                    pyautogui_code += f"\npyautogui.doubleClick({x}, {y}, button='left')"
                elif action_type == "right_single":
                    pyautogui_code += f"\npyautogui.click({x}, {y}, button='right')"
                elif action_type == "hover":
                    pyautogui_code += f"\npyautogui.moveTo({x}, {y})"
        
        elif action_type in ["finished"]:
            pyautogui_code = f"DONE"

        elif action_type in ["fail"]:
            pyautogui_code = f"FAIL"

        elif action_type in ["wait"]:
            pyautogui_code += f"time.sleep({action_inputs['time']})"

        else:
            return {
                'action_type': action_type,
                'parameters': action_inputs
            }
        # else:
            # pyautogui_code += f"\n# Unrecognized action type: {action_type}"

    return pyautogui_code

def pil_to_base64(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def linearize_accessibility_tree(accessibility_tree, platform="ubuntu"):

    if platform == "ubuntu":
        _attributes_ns = attributes_ns_ubuntu
        _state_ns = state_ns_ubuntu
        _component_ns = component_ns_ubuntu
        _value_ns = value_ns_ubuntu
    elif platform == "windows":
        _attributes_ns = attributes_ns_windows
        _state_ns = state_ns_windows
        _component_ns = component_ns_windows
        _value_ns = value_ns_windows
    else:
        raise ValueError("Invalid platform, must be 'ubuntu' or 'windows'")

    filtered_nodes = filter_nodes(ET.fromstring(accessibility_tree), platform)
    linearized_accessibility_tree = [
        "tag\tname\ttext\tclass\tdescription\tposition (top-left x&y)\tsize (w&h)"
    ]

    # Linearize the accessibility tree nodes into a table format
    for node in filtered_nodes:
        if node.text:
            text = (
                node.text
                if '"' not in node.text
                else '"{:}"'.format(node.text.replace('"', '""'))
            )

        elif node.get("{{{:}}}class".format(class_ns_windows), "").endswith(
            "EditWrapper"
        ) and node.get("{{{:}}}value".format(_value_ns)):
            node_text = node.get("{{{:}}}value".format(_value_ns), "")
            text = (
                node_text
                if '"' not in node_text
                else '"{:}"'.format(node_text.replace('"', '""'))
            )
        else:
            text = '""'

        linearized_accessibility_tree.append(
            "{:}\t{:}\t{:}\t{:}\t{:}\t{:}\t{:}".format(
                node.tag,
                node.get("name", ""),
                text,
                (
                    node.get("{{{:}}}class".format(_attributes_ns), "")
                    if platform == "ubuntu"
                    else node.get("{{{:}}}class".format(class_ns_windows), "")
                ),
                node.get("{{{:}}}description".format(_attributes_ns), ""),
                node.get("{{{:}}}screencoord".format(_component_ns), ""),
                node.get("{{{:}}}size".format(_component_ns), ""),
            )
        )

    return "\n".join(linearized_accessibility_tree)

def trim_accessibility_tree(linearized_accessibility_tree, max_tokens):
    # enc = tiktoken.encoding_for_model("gpt-4")
    # tokens = enc.encode(linearized_accessibility_tree)
    # if len(tokens) > max_tokens:
    #     linearized_accessibility_tree = enc.decode(tokens[:max_tokens])
    #     linearized_accessibility_tree += "[...]\n"
    return linearized_accessibility_tree


class OwlAgent:
    def __init__(
        self,
        model='',
        api_url='',
        api_key='',
        platform="ubuntu",
        max_tokens=1000,
        history_n=1,
        top_p=0.9,
        top_k=1.0,
        temperature=0.0,
        action_space="pyautogui",
        observation_type="screenshot",
        max_trajectory_length=50,
        a11y_tree_max_tokens=10000,
        use_seed=False,
        use_dashscope=False,
        runtime_conf: dict = {
            "infer_mode": "fn_call",
            "input_swap": False,
            "screen_height": 1080,
            "screen_width": 1920,
        }
    ):
        self.use_seed = use_seed
        self.use_dashscope = use_dashscope
        self.model = model
        self.platform = platform
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.top_k = top_k
        self.temperature = temperature
        self.action_space = action_space
        self.observation_type = observation_type
        self.max_trajectory_length = max_trajectory_length
        self.a11y_tree_max_tokens = a11y_tree_max_tokens
        self.runtime_conf = runtime_conf

        self.infer_mode = self.runtime_conf["infer_mode"]
        self.input_swap = self.runtime_conf["input_swap"]

        self.llm_client = OpenAI(base_url=api_url, api_key=api_key)
        dashscope.api_key = api_key

        self.thoughts = []
        self.actions = []
        self.observations = []
        self.history_images = []
        self.history_responses = []
        self.history_conclusion = []
        self.history_exe_results = []
        self.app_prompts = []
        
        self.customize_action_parser = parse_action_fncall_id
        
        if self.infer_mode == "fn_call":
            self.prompt_template = get_prompt_new
        else:
            raise NotImplementedError()

        self.history_n = history_n

    def predict(
        self, instruction: str, obs: Dict, last_action_after_obs: Dict = None
    ) -> List:
        """
        Predict the next action(s) based on the current observation.
        """

        use_dashscope = self.use_dashscope
        use_seed = self.use_seed
        tool_name = obs['tool_name']

        app_info = obs.get("exe_result", "None")

        self.app_prompts.append(app_info)

        print('---------', self.model)
        model_name = self.model

        if "claude" in model_name:
            # Convert bytes to PIL Image
            screenshot_bytes = obs["screenshot"]
            screenshot_image = Image.open(io.BytesIO(screenshot_bytes))
            
            # Calculate new size based on resize factor
            new_width, new_height = 1280, 720
            
            # Resize the image
            resized_image = screenshot_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Convert back to bytes
            output_buffer = io.BytesIO()
            resized_image.save(output_buffer, format='PNG')
            obs["screenshot"] = output_buffer.getvalue()

        step_idx = 0
        example_result_dir = "abc/osworld"
        instruction_id = example_result_dir.split('/')[-1]
        
        assert len(self.observations) == len(self.actions) and len(self.actions) == len(
            self.thoughts
        ), "The number of observations and actions should be the same."

        if len(self.observations) > self.max_trajectory_length:
            if self.max_trajectory_length == 0:
                _observations = []
                _actions = []
                _thoughts = []
            else:
                _observations = self.observations[-self.max_trajectory_length :]
                _actions = self.actions[-self.max_trajectory_length :]
                _thoughts = self.thoughts[-self.max_trajectory_length :]
        else:
            _observations = self.observations
            _actions = self.actions
            _thoughts = self.thoughts

        for previous_obs, previous_action, previous_thought in zip(
            _observations, _actions, _thoughts
        ):
            # {{{1
            if self.observation_type == "screenshot_a11y_tree":
                _screenshot = previous_obs["screenshot"]
                _linearized_accessibility_tree = previous_obs["accessibility_tree"]
            elif self.observation_type == "screenshot":
                _screenshot = previous_obs["screenshot"]
                _linearized_accessibility_tree = None
            else:
                raise ValueError(
                    "Invalid observation_type type: " + self.observation_type
                )  # 1}}}

        if last_action_after_obs is not None and self.infer_mode == "double_image":
            self.history_images.append(last_action_after_obs["screenshot"])
            pass
        self.history_images.append(obs["screenshot"])

        if self.observation_type in ["screenshot", "screenshot_a11y_tree"]:
            base64_image = obs["screenshot"]
            try:
                linearized_accessibility_tree = (
                    linearize_accessibility_tree(
                        accessibility_tree=obs["accessibility_tree"],
                        platform=self.platform,
                    )
                    if self.observation_type == "screenshot_a11y_tree"
                    else None
                )
            except:
                linearized_accessibility_tree = None

            if linearized_accessibility_tree:
                linearized_accessibility_tree = trim_accessibility_tree(
                    linearized_accessibility_tree, self.a11y_tree_max_tokens
                )

            if self.observation_type == "screenshot_a11y_tree":
                self.observations.append(
                    {
                        "screenshot": base64_image,
                        "accessibility_tree": linearized_accessibility_tree,
                    }
                )
            else:
                self.observations.append(
                    {"screenshot": base64_image, "accessibility_tree": None}
                )

        else:
            raise ValueError(
                "Invalid observation_type type: " + self.observation_type
            )  # }}}
        
        if len(self.history_conclusion) == 0:
            history_str = "No history. This is the first step."
        else:
            history_str = ""
            if len(self.history_exe_results) < len(self.history_conclusion):
                self.history_exe_results.append(obs['exe_result'])
            assert len(self.history_exe_results) == len(self.history_conclusion)
 
            for idx in range(len(self.history_conclusion)):
                if self.history_conclusion[idx] is not None:
                    history_str += "Step %d: "%(idx+1) + self.history_conclusion[idx] + '\n'
                if self.history_exe_results[idx] not in [None, ""]:
                    history_str += f"Tool call result: {self.history_exe_results[idx]}" + '\n'
        # print("infer_mode: ", tool_name)

        user_prompt = self.prompt_template(
            width=self.runtime_conf["screen_width"],
            height=self.runtime_conf["screen_height"],
            instruction=instruction,
            history=history_str,
            use_dashscope=use_dashscope,
            tool_name=tool_name,
            tool_list=obs['tool_list'],
            model=model_name
        )

        if len(self.history_images) > self.history_n:
            self.history_images = self.history_images[-self.history_n:]
            self.app_prompts = self.app_prompts[-(self.history_n - 1):]

        max_pixels = 3000 * 28 * 28
        min_pixels = 100 * 28 * 28
        messages, images = [], []
        if isinstance(self.history_images, bytes):
            self.history_images = [self.history_images]
        elif isinstance(self.history_images, np.ndarray):
            self.history_images = list(self.history_images)
        elif isinstance(self.history_images, list):
            pass
        else:
            raise TypeError(f"Unidentified images type: {type(self.history_images)}")
        max_image_nums_under_32k = int(32768*0.75/max_pixels*28*28)
        if len(self.history_images) > max_image_nums_under_32k:
            num_of_images = min(5, len(self.history_images))
            max_pixels = int(32768*0.75) // num_of_images

        for turn, image in enumerate(self.history_images):
            if len(images) >= 5:
                break
            try:
                image = Image.open(BytesIO(image))
            except Exception as e:
                raise RuntimeError(f"Error opening image: {e}")

            if image.width * image.height > max_pixels:
                """
                如果图片超过/低于像素限制，则计算一个缩放因子resize_factor，使图片的像素数缩小到等于或小于max_pixels。这个缩放因子是通过开平方根计算的，确保纵横比保持不变,这样原始的相对坐标可以不经转换直接复用
                """
                resize_factor = math.sqrt(max_pixels / (image.width * image.height))
                width, height = int(image.width * resize_factor), int(image.height * resize_factor)
                image = image.resize((width, height))
            if image.width * image.height < min_pixels:
                resize_factor = math.sqrt(min_pixels / (image.width * image.height))
                width, height = math.ceil(image.width * resize_factor), math.ceil(image.height * resize_factor)
                image = image.resize((width, height))

            if image.mode != "RGB":
                image = image.convert("RGB")

            images.append(image)

        messages = user_prompt
        # print(messages)
        
        image_num = 0

        if len(self.history_responses) > 0:
            for history_idx, history_response in enumerate(self.history_responses):
                # send at most history_n images to the model
                if history_idx + self.history_n > len(self.history_responses):

                    cur_image = images[image_num]
                    cur_app_prompt = self.app_prompts[image_num]
                    encoded_string = pil_to_base64(cur_image)
                    if use_dashscope:
                        messages[-1]['content'].append({"text": "Screenshot of step %d:\n"%(history_idx+1)})
                        messages[-1]['content'].append({"image": f"data:image/png;base64,{encoded_string}"})
                        messages[-1]['content'].append({"text": f"Action Response: {cur_app_prompt}"})
                    else:
                        messages[-1]['content'].append({"type": "text", "text": "Screenshot of step %d:\n"%(history_idx+1)})
                        messages[-1]['content'].append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_string}", "detail": "high",}})
                        messages[-1]['content'].append({"type": "text", "text": f"Action Response: {cur_app_prompt}"})
                    image_num += 1

            cur_image = images[image_num]
            encoded_string = pil_to_base64(cur_image)

            if use_dashscope:
                messages[-1]['content'].append({"text": "Current screenshot:\n"})
                messages[-1]['content'].append({"image": f"data:image/png;base64,{encoded_string}"})
            else:
                messages[-1]['content'].append({"type": "text", "text": "Current screenshot:\n"})
                messages[-1]['content'].append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_string}", "detail": "high",}})

            image_num += 1
        
        else:
                    
            cur_image = images[image_num]
            encoded_string = pil_to_base64(cur_image)
            if use_dashscope:
                messages[-1]['content'].append({"text": "Current screenshot:\n"})
                messages[-1]['content'].append({"image": f"data:image/png;base64,{encoded_string}"})
            else:
                messages[-1]['content'].append({"type": "text", "text": "Current screenshot:\n"})
                messages[-1]['content'].append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_string}", "detail": "high",}})
            
            image_num += 1
        
        try_times = 20

        # 生成prediction

        while True:
            print(f'[DEBUG]: trying times {try_times}')
            if try_times <= 0:
                print(f"Reach max retry times to fetch response from client, as error flag.")
                return "client error", ["DONE"], remove_base64_images(messages)

            try:
                if use_dashscope:
                    from dashscope import MultiModalConversation
                    if 'pre' in model_name:
                        dashscope.base_http_api_url = 'https://poc-dashscope.aliyuncs.com/api/v1'
                        dashscope.base_websocket_api_url = 'https://poc-dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation'
                    else:
                        dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
                        dashscope.base_websocket_api_url = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference'

                    completion = MultiModalConversation.call(
                        model=model_name,
                        messages=messages,
                        max_tokens=2048,
                        temperature=self.temperature,
                        top_p=self.top_p,
                        vl_high_resolution_images=True,
                        extra_body={"repetition_penalty": 1.05},
                    )
                    prediction = completion['output']['choices'][0]['message']['content'][0]['text']

                elif use_seed:
                    import requests
                    now_api = 0
                    api = [
                        dashscope.api_key
                    ]
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"{api[now_api]}"
                    }
                    
                    payload = {
                        "model": model_name,
                        "messages": messages,
                    }
                    
                    response = requests.post("http://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", headers=headers, json=payload)
                    print(response)
                    prediction = response.json()['choices'][0]['message']['content']

                else:
                    # OpenAI
                    response = self.llm_client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        max_tokens=2048,
                        temperature=self.temperature,
                        top_p=self.top_p,
                        extra_body={"repetition_penalty": 1.05},
                    )
                    prediction = response.choices[0].message.content
                
                parsed_responses = self.customize_action_parser(
                    prediction,
                    None,
                    self.runtime_conf["screen_height"],
                    self.runtime_conf["screen_width"],
                    model_name
                )
                break
            
            except Exception as e:
                # print(f"Error when fetching response from client, with response: {response}")
                print(f"Error when fetching response from client, with error: {e}")
                prediction = None
                try_times -= 1
                import time
                time.sleep(1)

        if prediction is None:
            return "client error", ["DONE"], remove_base64_images(messages)

        self.history_responses.append(prediction)
        self.thoughts.append(prediction)

        try:
            parsed_responses = self.customize_action_parser(
                prediction,
                None,
                self.runtime_conf["screen_height"],
                self.runtime_conf["screen_width"],
                model_name
            )
        except Exception as e:
            print(f"Parsing action error: {prediction}, with error:\n{e}")
            return f"Parsing action error: {prediction}, with error:\n{e}", ["DONE"], remove_base64_images(messages)

        this_step_conclusion = parsed_responses[0]['conclusion']
        self.history_conclusion.append(this_step_conclusion)

        actions = []
        for parsed_response in parsed_responses:
            if "action_type" in parsed_response:
                if parsed_response["action_type"] == "fail":
                    self.actions.append(actions)
                    return prediction, ["FAIL"], remove_base64_images(messages)
                elif parsed_response["action_type"] == "finished":
                    self.actions.append(actions)
                    return prediction, ["DONE"], remove_base64_images(messages)
            
            pyautogui_code = parsing_response_to_pyautogui_code(
                parsed_response,
                self.runtime_conf["screen_height"],
                self.runtime_conf["screen_width"],
                self.input_swap
            )
            actions.append(pyautogui_code)
        
        self.actions.append(actions)

        if len(self.history_responses) >= self.max_trajectory_length:
            # Default to FAIL if exceed max steps
            actions = ["FAIL"]

        return prediction, actions, remove_base64_images(messages)

    @backoff.on_exception(
        backoff.constant,
        # here you should add more model exceptions as you want,
        # but you are forbidden to add "Exception", that is, a common type of exception
        # because we want to catch this kind of Exception in the outside to ensure each example won't exceed the time limit
        (
            # General exceptions
            SSLError,
            # OpenAI exceptions
            openai.RateLimitError,
            openai.BadRequestError,
            openai.InternalServerError,
            # Google exceptions
            InvalidArgument,
            ResourceExhausted,
            InternalServerError,
            BadRequest,
            # Groq exceptions
            # todo: check
        ),
        interval=30,
        max_tries=10,
    )
    
    def reset(self, runtime_logger):
        self.thoughts = []
        self.actions = []
        self.observations = []
        self.history_images = []
        self.history_responses = []
        self.history_conclusion = []
        self.history_exe_results = []
        self.app_prompts = []
