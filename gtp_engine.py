#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import threading
import time
from pprint import pprint
from get_temperature import get_temperature

def cooling_gpu(temp_threshold=60):
    time.sleep(1)
    cpu, gpu, other, cpu_data, gpu_data, other_data = get_temperature()
    while cpu>temp_threshold or gpu>temp_threshold or other>temp_threshold:
        sleep_time = 5*max(cpu-temp_threshold, gpu-temp_threshold, other-temp_threshold)
        time.sleep(sleep_time)
        cpu, gpu, other, cpu_data, gpu_data, other_data = get_temperature()

class GTPEngine:
    def __init__(self, command, cwd=None):
        self.engine_start_time = time.time()
        self.command = command
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,  # For text I/O
            bufsize=1,
            cwd=cwd
        )
        self.stdout_thread = threading.Thread(target=self.read_stdout, daemon=True)
        self.stderr_thread = threading.Thread(target=self.read_stderr, daemon=True)
        self.stdout_lines = []
        self.stderr_lines = []
        self.ready = threading.Event()
        self.stdout_thread.start()
        self.stderr_thread.start()
        # Wait for ready
        self.wait_for_ready()

    def read_stdout(self):
        for line in iter(self.process.stdout.readline, ''):
            #line = line.rstrip('\n') # Only remove the trailing newline
            # Uncomment the next line to see stdout lines
            #print(f"Engine stdout: {line}")
            self.stdout_lines.append(line)

    def read_stderr(self):
        for line in iter(self.process.stderr.readline, ''):
            # Uncomment the next line to see stderr lines
            #print(f"\nEngine stderr: {line}", end='')
            if "GTP ready" in line:
                self.ready.set()  # Add this line to check stderr for "GTP ready"
            self.stderr_lines.append(line)

    def wait_for_ready(self, timeout=120):
        if not self.ready.wait(timeout):
            raise TimeoutError("GTP Engine did not become ready in time")
        else:
            end_time = time.time()
            duration = end_time - self.engine_start_time
            print(f'GTP ready cost {duration:>5.2f}s')

    def send_command(self, command, resp_num=1):
        # Clear any previous stdout_lines
        if len(self.stdout_lines):
            print(f'Remain stdout {self.stdout_lines}')
        self.stdout_lines.clear()

        # Send the command
        self.process.stdin.write(command + '\n')
        self.process.stdin.flush()

        # Read the response
        response = ''
        resp_count = 0
        while True:
            if len(self.stdout_lines) == 0:
                time.sleep(0.01)
                continue
            line = self.stdout_lines.pop(0)

            if line.startswith('=') or line.startswith('?'):
                response += line[1:].rstrip('\n') # Remove the '=' or '?', but keep the rest intact
                # Now read until blank line
                while True:
                    if len(self.stdout_lines) == 0:
                        time.sleep(0.01)
                        continue
                    next_line = self.stdout_lines.pop(0)
                    if next_line == '\n':
                        resp_count += 1
                        if resp_count == resp_num:
                            break  # End of response
                    response += '\n' + next_line.rstrip('\n')  # Append the line as is, including leading spaces
                break
            else:
                print('line', line)
        return response

    def close(self):
        self.process.terminate()
        self.stdout_thread.join()
        self.stderr_thread.join()

    def analyze_command(self, resp_num):
        interval = 100

        # Clear any previous stdout_lines
        if len(self.stdout_lines):
            print(f'Remain1 stdout {self.stdout_lines}')
        self.stdout_lines.clear()

        # Send the command
        self.process.stdin.write(f'kata-analyze b {interval}' + '\n')
        self.process.stdin.flush()

        # Read the response
        response = []
        resp_count = 0
        while True:
            if len(self.stdout_lines) == 0:
                time.sleep(0.01)
                continue
            line = self.stdout_lines.pop(0)

            if line.startswith('=') or line.startswith('?'):
                response += line[1:].rstrip('\n') # Remove the '=' or '?', but keep the rest intact
                # Now read until blank line
                # info move R16 visits 56 edgeVisits 56
                # utility -0.292949 winrate 0.36 scoreMean -0.83654 scoreStdev 13.5276 scoreLead -1 scoreSelfplay -1.52978
                # prior 0.0713674 lcb 0.353621 utilityLcb -0.304088 weight 175.554 order 0 pv R16 D16 D3 Q4 O17 C5 F4 D9 F17
                while True:
                    if len(self.stdout_lines) == 0:
                        time.sleep(interval/1000)
                        continue
                    next_line = self.stdout_lines.pop(0)

                    r = next_line.rstrip('\n').split()
                    m = {
                        #'move': r[2],
                        'visits': int(r[4]),
                        #'winrate': r[10],
                        #'scoreLead': r[16],
                        #'pv': r[30:]
                    }
                    response.append(m)

                    resp_count += 1
                    if resp_count == resp_num:
                        self.process.stdin.write('\n')
                        self.process.stdin.flush()
                        break

                    temp_threshold = 75
                    cpu, gpu, other, cpu_data, gpu_data, other_data = get_temperature()
                    if cpu>temp_threshold or gpu>temp_threshold or other>temp_threshold:
                        self.process.stdin.write('\n')
                        self.process.stdin.flush()
                        break

                break
            else:
                print('line', line)

        # Clear any previous stdout_lines
        if len(self.stdout_lines):
            print(f'Remain3 stdout {self.stdout_lines}')
        self.stdout_lines.clear()

        return response

def send_one_command(gtp_engine):
    start_time = time.time()

    response = gtp_engine.send_command("boardsize 19")
    response = gtp_engine.send_command("clear_board")
    response = gtp_engine.send_command("komi 7.5")
    response = gtp_engine.send_command("play B Q16")
    response = gtp_engine.send_command("play W D4")
    response = gtp_engine.send_command('showboard')
    print(response)
    response = gtp_engine.send_command(f"genmove b")
    move = response.strip()
    print(move)
    response = gtp_engine.send_command('showboard')
    print(response)

    end_time = time.time()
    duration = end_time - start_time
    print(f'\ncost {duration:>5.2f}s')

def batch_send_command(gtp_engine):
    start_time = time.time()

    cmd_str = ''
    resp_num = 0

    cmd_str += f"boardsize 19\n"
    resp_num += 1
    cmd_str += f"clear_board\n"
    resp_num += 1
    cmd_str += f"komi 7.5\n"
    resp_num += 1
    cmd_str += f'play B Q16\n'
    resp_num += 1
    cmd_str += f'play W D4\n'
    resp_num += 1
    cmd_str += f'showboard\n'
    resp_num += 1
    cmd_str += f'genmove b\n'
    resp_num += 1
    cmd_str += f'showboard\n'
    resp_num += 1
    response = gtp_engine.send_command(cmd_str, resp_num)
    print(response)

    end_time = time.time()
    duration = end_time - start_time
    print(f'\ncost {duration:>5.2f}s')

def analyze_command(gtp_engine, max_visits=10):
    start_time = time.time()
    visits = 0
    while visits<max_visits:
        response = gtp_engine.analyze_command(3)
        print(response)
        visits = response[-1].get('visits')
        cooling_gpu(70)
    end_time = time.time()
    duration = end_time - start_time
    print(f'cost {duration:>5.2f}s')

def test():
    # Start GTP engine
    katago_cfg_filename = '/Users/zliu/go/katago/gtp_normal_v500.cfg'
    engine_command = [
        "/Users/zliu/go/katago/katago-metal-1move", "gtp", 
        "-config", katago_cfg_filename,
        "-model", "/Users/zliu/go/katago/b28.bin.gz",
    ]
    gtp_engine = GTPEngine(engine_command)

    analyze_command(gtp_engine, max_visits=1000)
    #send_one_command(gtp_engine)
    #batch_send_command(gtp_engine)

    # Stop GTP engine
    gtp_engine.close()

if __name__ == "__main__":
    test()
