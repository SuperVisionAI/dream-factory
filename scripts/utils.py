# Copyright 2021 - 2022, Bill Kennedy
# SPDX-License-Identifier: MIT

import threading
import time
import datetime
import shlex
import subprocess
import sys
import unicodedata
import re
import random
import os
from os.path import exists
from datetime import datetime as dt
from datetime import date
from pathlib import Path
from collections import deque
from PIL.PngImagePlugin import PngImageFile, PngInfo


# maintains the info in each input file [prompt] section
class PromptSection():
    def __init__(self, tokens, min_pick, max_pick, delim):
        self.tokens = tokens
        self.min_pick = min_pick
        self.max_pick = max_pick
        self.delim = delim

    def debug_print(self):
        print("\n*** Printing contents of PromptSection: ***")
        print("min pick: " + str(self.min_pick))
        print("max pick: " + str(self.max_pick))
        print("delim: (" + self.delim + ')')
        if len(self.tokens) > 0:
            print("tokens:")
            for x in self.tokens:
                print(">> " + x)
        else:
            print("tokens list is empty")
        print('\n')

# for easy management of input files
# input_path is the directory of the input images to use
class InputManager():
    def __init__(self, input_path):
        # a list of all the files we're using as inputs
        self.files = list()
        if input_path != "":
            self.input_directory = input_path

            # populate the list with the given init directory
            for x in os.listdir(input_path):
                if x.endswith('.jpg') or x.endswith('.png'):
                    self.files.append(x)

    # pick a random file from the list
    def pick_random(self):
        if len(self.files) > 0:
            x = random.randint(0, len(self.files)-1)
            return self.files[x]
        else:
            return ""

    def debug_print_files(self):
        if len(self.files) > 0:
            print("Listing " + str(len(self.files)) + " total files in '" + self.input_directory + "':")
            for x in self.files:
                print(x)
        else:
            print("Input image directory '" + self.input_directory + "' is empty; input images will not be used.")

# for easy management of prompts
class PromptManager():
    def __init__(self, prompt_file):
        # text file containing all of the prompt/style/etc info
        self.prompt_file_name = prompt_file

        # dictionary of config info w/ initial defaults
        self.config = {}
        self.reset_config_defaults()

        # list for config info
        self.conf = list()
        # list of PromptSection
        self.prompts = list()

        self.__init_config(self.conf, "config")
        self.__init_prompts(self.prompts, "prompts")

        #self.debug_print()

    # init the prompts list
    def __init_prompts(self, which_list, search_text):
        with open(self.prompt_file_name) as f:
            lines = f.readlines()

            found_header = False
            search_header = '[' + search_text

            tokens = list()
            ps = PromptSection(tokens, 1, 1, self.config.get('delim'))

            # find the search text and read until the next search header
            for line in lines:
                # ignore comments and strip whitespace
                line = line.strip().split('#', 1)
                line = line[0]

                # if we already found the header we want and we see another header,
                if found_header and len(line) > 0 and line.startswith('['):
                    # save PromptSection
                    which_list.append(ps)

                    # start a new PS
                    tokens = list()
                    ps = PromptSection(tokens, 1, 1,self.config.get('delim'))

                    # look for next prompt section
                    found_header = False

                # found the search header
                if search_header.lower() in line.lower() and line.endswith(']'):
                    found_header = True

                    # check for optional args
                    args = line.strip(search_header).strip(']').strip()
                    vals = shlex.split(args, posix=False)

                    # grab min/max args
                    if len(vals) > 0:
                        if '-' in vals[0]:
                            minmax = vals[0].split('-')
                            if len(minmax) > 0:
                                ps.min_pick = minmax[0].strip()
                                if len(minmax) > 1:
                                    ps.max_pick = minmax[1].strip()
                        else:
                            ps.min_pick = vals[0]
                            ps.max_pick = vals[0]

                        # grab delim arg
                        if len(vals) > 1:
                            if vals[1].startswith('\"') and vals[1].endswith('\"'):
                                ps.delim = vals[1].strip('\"')

                    line = ""

                if len(line) > 0 and found_header:
                    ps.tokens.append(line)

            # save final PromptSection if not empty
            if len(ps.tokens) > 0:
                which_list.append(ps)


    # init the config list
    def __init_config(self, which_list, search_text):
        with open(self.prompt_file_name) as f:
            lines = f.readlines()

            search_header = '[' + search_text + ']'
            found_header = False

            # find the search text and read until the next search header
            for line in lines:
                # ignore comments and strip whitespace
                line = line.strip().split('#', 1)
                line = line[0]

                # if we already found the header we want and we see another header, stop
                if found_header and len(line) > 0 and line[0] == '[':
                    break

                # found the search header
                if search_header.lower() == line.lower():
                    found_header = True
                    line = ""

                if len(line) > 0 and found_header:
                    #print(search_header + ": " + line)
                    which_list.append(line)


    # resets config options back to defaults
    def reset_config_defaults(self):
        self.config = {
            'mode' : "combination",
            'sd_low_memory' : "no",
            'sd_low_mem_turbo' : "no",
            'seed' : -1,
            'width' : 512,
            'height' : 512,
            'steps' : 80,
            'scale' : 7.5,
            'min_scale' : 7.5,
            'max_scale' : 7.5,
            'samples' : 1,
            'batch_size' : 1,
            'input_image' : "",
            'random_input_image_dir' : "",
            'strength' : 0.75,
            'min_strength' : 0.75,
            'max_strength' : 0.75,
            'delim' : " ",
            'use_upscale' : "no",
            'upscale_amount' : 2.0,
            'upscale_face_enh' : "no",
            'upscale_keep_org' : "no",
            'outdir' : "output"
        }


    def debug_print(self):
        if len(self.prompts) > 0:
            print("\nPS contents:\n")
            for x in self.prompts:
                x.debug_print()
        else:
            print("prompts list is empty")

    # update config variables if there were changes in the prompt file
    def handle_config(self):
        if len(self.conf) > 0:
            for line in self.conf:
                # check for lines that start with '!' and contain '='
                ss = re.search('!(.+?)=', line)
                if ss:
                    command = ss.group(1).lower().strip()
                    value = line.split("=",1)[1].lower().strip()

                    if command == 'width':
                        if value != '':
                            try:
                                int(value)
                            except:
                                print("*** WARNING: specified 'WIDTH' is not a valid number; it will be ignored!")
                            else:
                                self.config.update({'width' : value})

                    elif command == 'height':
                        if value != '':
                            try:
                                int(value)
                            except:
                                print("*** WARNING: specified 'HEIGHT' is not a valid number; it will be ignored!")
                            else:
                                self.config.update({'height' : value})

                    elif command == 'seed':
                        if value != '':
                            try:
                                int(value)
                            except:
                                print("*** WARNING: specified 'SEED' is not a valid number; it will be ignored!")
                            else:
                                self.config.update({'seed' : value})

                    elif command == 'steps':
                        if value != '':
                            try:
                                int(value)
                            except:
                                print("*** WARNING: specified 'STEPS' is not a valid number; it will be ignored!")
                            else:
                                self.config.update({'steps' : value})

                    elif command == 'scale':
                        if value != '':
                            try:
                                float(value)
                            except:
                                print("*** WARNING: specified 'SCALE' is not a valid number; it will be ignored!")
                            else:
                                self.config.update({'scale' : value})

                    elif command == 'min_scale':
                        if value != '':
                            try:
                                float(value)
                            except:
                                print("*** WARNING: specified 'MIN_SCALE' is not a valid number; it will be ignored!")
                            else:
                                self.config.update({'min_scale' : value})

                    elif command == 'max_scale':
                        if value != '':
                            try:
                                float(value)
                            except:
                                print("*** WARNING: specified 'MAX_SCALE' is not a valid number; it will be ignored!")
                            else:
                                self.config.update({'max_scale' : value})

                    elif command == 'samples':
                        if value != '':
                            try:
                                int(value)
                            except:
                                print("*** WARNING: specified 'SAMPLES' is not a valid number; it will be ignored!")
                            else:
                                self.config.update({'samples' : value})

                    elif command == 'batch_size':
                        if value != '':
                            try:
                                int(value)
                            except:
                                print("*** WARNING: specified 'BATCH_SIZE' is not a valid number; it will be ignored!")
                            else:
                                self.config.update({'batch_size' : value})

                    elif command == 'strength':
                        if value != '':
                            try:
                                float(value)
                            except:
                                print("*** WARNING: specified 'STRENGTH' is not a valid number; it will be ignored!")
                            else:
                                self.config.update({'strength' : value})

                    elif command == 'min_strength':
                        if value != '':
                            try:
                                float(value)
                            except:
                                print("*** WARNING: specified 'MIN_STRENGTH' is not a valid number; it will be ignored!")
                            else:
                                self.config.update({'min_strength' : value})

                    elif command == 'max_strength':
                        if value != '':
                            try:
                                float(value)
                            except:
                                print("*** WARNING: specified 'MAX_STRENGTH' is not a valid number; it will be ignored!")
                            else:
                                self.config.update({'max_strength' : value})

                    elif command == 'sd_low_memory':
                        if value == 'yes' or value == 'no':
                            self.config.update({'sd_low_memory' : value})

                    elif command == 'sd_low_mem_turbo':
                        if value == 'yes' or value == 'no':
                            self.config.update({'sd_low_mem_turbo' : value})

                    elif command == 'use_upscale':
                        if value == 'yes' or value == 'no':
                            self.config.update({'use_upscale' : value})

                    elif command == 'upscale_amount':
                        if value != '':
                            try:
                                float(value)
                            except:
                                print("*** WARNING: specified 'UPSCALE_AMOUNT' is not a valid number; it will be ignored!")
                            else:
                                self.config.update({'upscale_amount' : value})

                    elif command == 'upscale_face_enh':
                        if value == 'yes' or value == 'no':
                            self.config.update({'upscale_face_enh' : value})

                    elif command == 'upscale_keep_org':
                        if value == 'yes' or value == 'no':
                            self.config.update({'upscale_keep_org' : value})

                    elif command == 'mode':
                        if value == 'random' or value == 'combination':
                            self.config.update({'mode' : value})

                    elif command == 'input_image':
                        if value != '':
                            self.config.update({'input_image' : value})

                    elif command == 'random_input_image_dir':
                        if value != '':
                            self.config.update({'random_input_image_dir' : value})

                    elif command == 'delim':
                        if value != '':
                            if value.startswith('\"') and value.endswith('\"'):
                                self.config.update({'delim' : value.strip('\"')})
                                #print("New delim: \"" + self.config.get('delim')  + "\"")
                            else:
                                print("*** WARNING: prompt file command DELIM value (" + value + ") not understood (make sure to put quotes around it)! ***")
                                time.sleep(1.5)

                    else:
                        print("*** WARNING: prompt file command not recognized: " + command.upper() + " (it will be ignored)! ***")
                        time.sleep(1.5)


    # create a random prompt from the information in the prompt file
    def pick_random(self):
        fragments = 0
        full_prompt = ""
        tokens = list()

        if len(self.prompts) > 0:
            # iterate through each PromptSection to build the prompt
            for ps in self.prompts:
                fragment = ""
                picked = 0
                # decide how many tokens to pick
                x = random.randint(int(ps.min_pick), int(ps.max_pick))

                # pick token(s)
                if len(ps.tokens) >= x:
                    tokens = ps.tokens.copy()
                    for i in range(x):
                        z = random.randint(0, len(tokens)-1)
                        if picked > 0:
                            fragment += ps.delim
                        fragment += tokens[z]
                        del tokens[z]
                        picked += 1
                else:
                    # not enough tokens to take requested amount, take all
                    for t in ps.tokens:
                        if picked > 0:
                            fragment += ps.delim
                        fragment += t
                        picked += 1

                # add this fragment to the overall prompt
                if fragment != "":
                    if fragments > 0:
                        if not (fragment.startswith(',') or fragment.startswith(';')):
                            full_prompt += self.config.get('delim')
                    full_prompt += fragment
                    fragments += 1

        full_prompt = full_prompt.replace(",,", ",")
        full_prompt = full_prompt.replace(", ,", ",")
        full_prompt = full_prompt.replace(" and,", ",")
        full_prompt = full_prompt.replace(" by and ", " by ")
        full_prompt = full_prompt.strip().strip(',')

        return full_prompt











# for easy reading of prompt/config files
class TextFile():
    def __init__(self, filename):
        self.lines = deque()
        if exists(filename):
            with open(filename) as f:
                l = f.readlines()

            for x in l:
                # remove newline and whitespace
                x = x.strip('\n').strip();
                # remove comments
                x = x.split('#', 1)[0].strip();
                if x != "":
                    # these lines are actual prompts
                    self.lines.append(x)

    def next_line(self):
        return self.lines.popleft()

    def lines_remaining(self):
        return len(self.lines)


# Taken from https://github.com/django/django/blob/master/django/utils/text.py
# Using here to make filesystem-safe directory names
def slugify(value, allow_unicode=False):
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    value = re.sub(r'[-\s]+', '-', value).strip('-_')
    # added in case of very long filenames due to multiple prompts
    return value[0:180]


# gets just filename from absolute path
def filename_from_abspath(fpath):
    filename = fpath
    if '\\' in fpath:
        filename = fpath.rsplit('\\', 1)[1]
    elif '/' in fpath:
        filename = fpath.rsplit('/', 1)[1]
    return filename

# gets just path from absolute path + filename
def path_from_abspath(fpath):
    path = fpath
    if '\\' in fpath:
        path = fpath.rsplit('\\', 1)[0]
    elif '/' in fpath:
        path = fpath.rsplit('/', 1)[0]
    return path


# creates the full command to invoke SD with our specified params
# and selected prompt + input image
def create_command(command, output_dir_ext):
    output_dir_ext = filename_from_abspath(output_dir_ext)
    if '.' in output_dir_ext:
        output_dir_ext = output_dir_ext.split('.', 1)[0]
    output_folder = command.get('outdir') + '/' + str(date.today()) + '-' + str(output_dir_ext)

    py_command = "python scripts_mod/txt2img.py"
    if command.get('sd_low_memory') == "yes":
        py_command = "python scripts_mod/optimized_txt2img.py"

    if command.get('input_image') != "":
        py_command = "python scripts_mod/img2img.py"
        if command.get('sd_low_memory') == "yes":
            py_command = "python scripts_mod/optimized_img2img.py"

    if command.get('sd_low_memory') == "yes" and command.get('sd_low_mem_turbo') == "yes":
        py_command += " --turbo"

    py_command += " --skip_grid" \
        + " --n_iter " + str(command.get('samples')) \
        + " --prompt \"" + str(command.get('prompt')) + "\"" \
        + " --ddim_steps " + str(command.get('steps')) \
        + " --scale " + str(command.get('scale')) \
        + " --seed " + str(command.get('seed'))

    if command.get('input_image') != "":
        py_command += " --init-img \"../" + str(command.get('input_image')) + "\"" + " --strength " + str(command.get('strength'))
    else:
        py_command += " --W " + str(command.get('width')) + " --H " + str(command.get('height'))

    py_command += " --outdir \"../" + output_folder + "\""

    return py_command
