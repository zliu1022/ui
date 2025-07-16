#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from pymongo import MongoClient, UpdateOne

from gtp_engine import GTPEngine
from config import db_name

def sgf_coord_to_xy(coord):
    col_letter = coord[0]
    row_letter = coord[1]
    x = ord(col_letter) - ord('a')
    y = ord(row_letter) - ord('a')
    return x, y

def xy_to_sgf_coord(x, y):
    col_letter = chr(x + ord('a'))
    row_letter = chr(y + ord('a'))
    return col_letter + row_letter

def xy_to_gtp_coord(x, y, board_size):
    letters = 'ABCDEFGHJKLMNOPQRST'  # Skip 'I'
    col_letter = letters[x]
    row_number = board_size - y
    return f"{col_letter}{row_number}"

def gtp_coord_to_xy(coord, board_size):
    letters = 'ABCDEFGHJKLMNOPQRST'
    col_letter = coord[0]
    row_number = int(coord[1:])
    x = letters.index(col_letter)
    y = board_size - row_number
    return x, y

class GoProblemSolver:
    def __init__(self, problem_doc, keepsize=False):
        self.problem_doc = problem_doc
        self.publicid = problem_doc["publicid"]
        self.prepos = problem_doc["prepos"]
        self.answers = problem_doc["answers"]
        self.blackfirst = problem_doc.get("blackfirst", True)
        self.komi = 7.5
        if keepsize:
            self.board_size = problem_doc.get("size")
            size = self.compute_minimal_board()
            self.transformed_prepos = self.fill_black_in_empty_board(size)

            transformed_answers = []
            for answer in self.answers:
                if answer.get('ty') == 1 and answer.get('st') == 2:
                    transformed_answers.append(answer)
            self.transformed_answers = transformed_answers

        else:
            size = self.compute_minimal_board()
            self.board_size = size
            self.transform_coordinates()
        self.bw_flag = False #交换黑白，默认不交换
        self.ko_symmetry = False #对于劫活，制造对称死活，相当于劫财，默认不需要劫财

    def compute_minimal_board(self):
        # Collect all coordinates
        positions = []
        # Preposition stones
        for coord in self.prepos.get('b', []):
            positions.append(sgf_coord_to_xy(coord))
        for coord in self.prepos.get('w', []):
            positions.append(sgf_coord_to_xy(coord))
        # Answer moves (only ty==1 and st==2)
        for answer in self.answers:
            if answer.get('ty') == 1 and answer.get('st') == 2:
                positions.extend([sgf_coord_to_xy(coord) for coord in answer.get('p', [])])

        xs = [pos[0] for pos in positions]
        ys = [pos[1] for pos in positions]

        # Determine which corner the problem is closest to
        corners = {
            'top-left': (0, 0),
            'top-right': (18, 0),
            'bottom-left': (0, 18),
            'bottom-right': (18, 18)
        }

        corner_distances = {}
        for corner_name, (cx, cy) in corners.items():
            # Chebyshev 距离，在网格游戏（如围棋）中会使用，表示在网格上移动的最大步数
            distances = [max(abs(x - cx), abs(y - cy)) for x, y in positions] 
            #distances = [((x - cx)**2 + (y - cy)**2)**0.5 for x, y in positions]
            max_distance = max(distances)
            corner_distances[corner_name] = max_distance

        # Select the corner with the smallest maximum distance
        self.corner = min(corner_distances, key=corner_distances.get)
        self.corner_coords = corners[self.corner]

        # Compute minimal board size based on the selected corner
        cx, cy = self.corner_coords
        x_distances = [abs(x - cx) for x in xs]
        y_distances = [abs(y - cy) for y in ys]
        max_x_distance = max(x_distances)
        max_y_distance = max(y_distances)
        size = max(max_x_distance, max_y_distance) + 2  # Add 1 to include the furthest stone
        # Ensure size is odd
        if size % 2 == 0:
            size += 1
        #self.board_size = size
        self.positions = positions
        self.min_x = min(xs)
        self.max_x = max(xs)
        self.min_y = min(ys)
        self.max_y = max(ys)

        return size

    def transform_coordinates(self):
        # Adjust positions to keep the proximity to the selected corner
        cx, cy = self.corner_coords
        # Define mapping functions based on corner coordinates
        if cx == 0:
            #x_map = lambda x: x - self.min_x
            x_map = lambda x: x - self.min_x
        elif cx == 18:
            x_map = lambda x: cx - x
        if cy == 0:
            #y_map = lambda y: y - self.min_y
            y_map = lambda y: y
        elif cy == 18:
            y_map = lambda y: cy - y

        # Apply mapping to positions
        self.transformed_positions = [(x_map(x), y_map(y)) for x, y in self.positions]

        # Update prepos
        self.transformed_prepos = {'b': [], 'w': []}
        for color in ['b', 'w']:
            coords = self.prepos.get(color, [])
            #print(coords)
            positions = [sgf_coord_to_xy(coord) for coord in coords]
            #print(positions)
            transformed_positions = [(x_map(x), y_map(y)) for x, y in positions]
            #print(transformed_positions)
            new_coords = [xy_to_sgf_coord(x, y) for x, y in transformed_positions]
            #print(new_coords)
            self.transformed_prepos[color] = new_coords

        # Update answers
        transformed_answers = []
        for answer in self.answers:
            if answer.get('ty') == 1 and answer.get('st') == 2:
                coords = answer.get('p', [])
                positions = [sgf_coord_to_xy(coord) for coord in coords]
                transformed_positions = [(x_map(x), y_map(y)) for x, y in positions]
                new_coords = [xy_to_sgf_coord(x, y) for x, y in transformed_positions]
                new_answer = answer.copy()
                new_answer['p'] = new_coords
                transformed_answers.append(new_answer)
        self.transformed_answers = transformed_answers

    def generate_sgf_str(self, with_answer=True):
        size = self.board_size
        sgf = f"(;FF[4]GM[1]SZ[{size}]KM[{self.komi}]C[publicid: {self.publicid}]"
        if self.blackfirst: 
            sgf += f"PL[B]\n"
        else:
            sgf += f"PL[W]\n"

        # Add preposition stones
        if self.transformed_prepos.get('b'):
            stones = ''.join(f"[{coord}]" for coord in self.transformed_prepos['b'])
            sgf += f"AB{stones}\n"
        if self.transformed_prepos.get('w'):
            stones = ''.join(f"[{coord}]" for coord in self.transformed_prepos['w'])
            sgf += f"AW{stones}\n"

        if with_answer:
            # Now add the variations
            for answer in self.transformed_answers:
                moves = answer.get('p', [])
                if not moves:
                    continue
                variation = ''
                current_color = 'B' if self.blackfirst else 'W'
                for move in moves:
                    variation += f";{current_color}[{move}]"
                    current_color = 'W' if current_color == 'B' else 'B'
                sgf += f"({variation})\n"

        sgf += ")\n"
        return sgf

    def save_as_sgf(self, filename=None):
        if filename is None:
            if not self.bw_flag:
                filename = f"{self.publicid}.sgf"
            else:
                filename = f"{self.publicid}_bw.sgf"
        self.filename = filename
        sgf = self.generate_sgf_str(False)
        with open(filename, 'w') as f:
            f.write(sgf)
        return sgf

    def is_valid_move(self, move):
        if not move:
            return False
        if move.lower() == 'resign' or move.lower() == 'pass':
            return True
        letters = 'ABCDEFGHJKLMNOPQRST'
        if len(move) < 2:
            return False
        col_letter = move[0]
        row_number_str = move[1:]
        if col_letter not in letters:
            return False
        if not row_number_str.isdigit():
            return False
        row_number = int(row_number_str)
        if not (1 <= row_number <= 19):
            return False
        return True

    def solve_problem(self, gtp_engine):
        size = self.board_size

        start_time = time.time()
        cmd_str = ''
        resp_num = 0

        cmd_str += f"boardsize {size}\n"
        resp_num += 1
        #response = gtp_engine.send_command(f"boardsize {size}")
        cmd_str += f"clear_board\n"
        resp_num += 1
        #response = gtp_engine.send_command("clear_board")

        cmd_str += f"komi {self.komi}\n"
        resp_num += 1

        # Place the initial stones
        for coord in self.transformed_prepos.get('b', []):
            x, y = sgf_coord_to_xy(coord)
            gtp_coord = xy_to_gtp_coord(x, y, size)
            cmd_str += f'play B {gtp_coord}\n'
            resp_num += 1
            #response = gtp_engine.send_command(f"play B {gtp_coord}")
        for coord in self.transformed_prepos.get('w', []):
            x, y = sgf_coord_to_xy(coord)
            gtp_coord = xy_to_gtp_coord(x, y, size)
            cmd_str += f'play W {gtp_coord}\n'
            resp_num += 1
            #response = gtp_engine.send_command(f"play W {gtp_coord}")
        response = gtp_engine.send_command(cmd_str, resp_num)

        end_time = time.time()
        duration = end_time - start_time
        print(f'{duration:>5.2f}s', end=' ')

        #response = gtp_engine.send_command('showboard')
        #print(response)

        # Now generate move
        color = 'b' if self.blackfirst else 'w'
        response = gtp_engine.send_command(f"genmove {color.upper()}")
        move = response.strip()
        # Convert move to x,y
        if not self.is_valid_move(move):
            print(f"Invalid move '{move}' response '{response}' ")
            return False, {'color':color, 'move': move}
        engine_move_sym = '--'
        if move.lower() == 'resign' or move.lower() == 'pass':
            print(f"{color} {move:>6}", end=' ')
            engine_move = move.lower()
        else:
            print(f"{color} {move:>6}", end=' ')
            x, y = gtp_coord_to_xy(move, size)

            sgf_move = xy_to_sgf_coord(x, y)
            engine_move = sgf_move
            if self.ko_symmetry:
                # Reflect across both axes for central symmetry
                x_reflected = 18 - x
                y_reflected = 18 - y
                coord_reflected = xy_to_sgf_coord(x_reflected, y_reflected)

                engine_move_sym = coord_reflected
                move_sym = xy_to_gtp_coord(x_reflected, y_reflected, self.board_size)
                print(f"{move_sym:>6}", end=' ')

        # Now compare engine_move to answers
        matching = False
        for answer in self.transformed_answers:
            answer_moves = answer.get('p', [])
            if answer_moves and (answer_moves[0] == engine_move or answer_moves[0] == engine_move_sym):
                matching = True
                print("OK ", end=' ')
                return True, {'color':color, 'move': move}
        if not matching:
            print("ERR", end=' ')
            return False, {'color':color, 'move': move}
        # Optionally, continue playing out the sequence

    def swap_black_white_with_transform(self):
        # Swap the preposition stones
        self.prepos['b'], self.prepos['w'] = self.prepos.get('w', []), self.prepos.get('b', [])
        # Swap the blackfirst flag
        self.blackfirst = not self.blackfirst
        # After swapping, we need to re-apply the coordinate transformations
        self.transform_coordinates()

        self.bw_flag = True

    def swap_black_white(self):
        # Swap the preposition stones
        self.prepos['b'], self.prepos['w'] = self.prepos.get('w', []), self.prepos.get('b', [])
        # Swap the blackfirst flag
        self.blackfirst = not self.blackfirst
        self.bw_flag = True

        size = self.compute_minimal_board()
        self.transformed_prepos = self.fill_black_in_empty_board(size)
        self.transformed_answers = self.answers

    def fill_black_in_empty_board(self, size):
        prepos = self.prepos

        # Collect existing stones and find the bounding box of the problem area
        existing_stones = set()
        for color in ['b', 'w']:
            for coord in prepos[color]:
                x, y = sgf_coord_to_xy(coord)
                existing_stones.add((x, y))
        xs = [x for x, y in existing_stones]
        ys = [y for x, y in existing_stones]
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)

        # Calculate distances to board edges
        left_distance = min_x
        right_distance = 18 - max_x
        bottom_distance = min_y
        top_distance = 18 - max_y
        
        # Determine sides not adjacent to the edge (distance >= 3)
        sides_adjacent_to_edge = set()
        if left_distance < 3:
            sides_adjacent_to_edge.add('left')
        if right_distance < 3:
            sides_adjacent_to_edge.add('right')
        if top_distance < 3:
            sides_adjacent_to_edge.add('top')
        if bottom_distance < 3:
            sides_adjacent_to_edge.add('bottom')

        # 计算黑komi的范围，无论是否交换黑白，最后总是黑包围白，最外面一圈黑也计入komi
        komi_x_min = 0  if 'left'  in sides_adjacent_to_edge else max(min_x+1,0) 
        komi_x_max = 18 if 'right' in sides_adjacent_to_edge else min(max_x-1,18)  
        komi_y_min = 0  if 'bottom' in sides_adjacent_to_edge else max(min_y+1,0) 
        komi_y_max = 18 if 'top'    in sides_adjacent_to_edge else min(max_y-1,18) 
        def is_in_problem_area(x, y):
            return (komi_x_min <= x <= komi_x_max) and (komi_y_min <= y <= komi_y_max)
        komi = 0
        for x in range(19):
            for y in range(19):
                if not is_in_problem_area(x, y):
                    komi += 1
        #print(f'komi {komi} x {komi_x_min} - {komi_x_max} y {komi_y_min} - {komi_y_max}', end='')
        self.komi = komi

        # Expand the excluded area by 1 in directions not adjacent to the edge
        # 如靠近边界，直接赋予边界值；不靠近边界，扩大1，然后和边界比较，得到合理的取值；
        exclusions_x_min = 0  if 'left'  in sides_adjacent_to_edge else max(min_x - 1,0) 
        exclusions_x_max = 18 if 'right' in sides_adjacent_to_edge else min(max_x + 1,18) 
        exclusions_y_min = 0  if 'bottom' in sides_adjacent_to_edge else max(min_y - 1,0) 
        exclusions_y_max = 18 if 'top'    in sides_adjacent_to_edge else min(max_y + 1,18) 

        def is_in_excluded_area(x, y):
            return (exclusions_x_min <= x <= exclusions_x_max) and (exclusions_y_min <= y <= exclusions_y_max)
        
        # Copy the original positions to avoid modifying the input directly
        prepos_new = {'b': prepos['b'].copy(), 'w': prepos['w'].copy()}

        # Fill the board with black stones in the alternating pattern, avoiding the excluded area
        for x in range(19):
            if x % 2 == 0:
                y_values = range(18, -1, -2)
            else:
                y_values = range(17, -1, -2)
            for y in y_values:
                if (x, y) not in existing_stones and not is_in_excluded_area(x, y):
                    coord = xy_to_sgf_coord(x, y)
                    prepos_new['b'].append(coord)
                    existing_stones.add((x, y))

        return prepos_new

    def symmetry_fill_black_in_empty_board(self):
        prepos = self.prepos

        # Collect existing stones and find the bounding box of the problem area
        existing_stones = set()
        xs = []
        ys = []
        for color in ['b', 'w']:
            for coord in prepos[color]:
                x, y = sgf_coord_to_xy(coord)
                existing_stones.add((x, y))
                xs.append(x)
                ys.append(y)
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)

        # Calculate distances to board edges
        left_distance = min_x
        right_distance = 18 - max_x
        bottom_distance = min_y
        top_distance = 18 - max_y

        # Determine sides adjacent to the edge (exact adjacency, distance == 0)
        sides_adjacent_to_edge = set()
        if left_distance < 3:
            sides_adjacent_to_edge.add('left')
        if right_distance < 3:
            sides_adjacent_to_edge.add('right')
        if top_distance < 3:
            sides_adjacent_to_edge.add('top')
        if bottom_distance < 3:
            sides_adjacent_to_edge.add('bottom')

        # Copy prepos to avoid modifying the input directly
        prepos_new = {'b': prepos['b'].copy(), 'w': prepos['w'].copy()}

        sides_adjacent_to_edge_reflected = set()
        # If the problem area is adjacent to 1 or 2 edge, create a symmetric problem area
        if len(sides_adjacent_to_edge) <= 2:

            # Reflect the problem area across the board to create symmetry
            reflected_stones = {'b': [], 'w': []}
            for color in ['b', 'w']:
                for coord in prepos[color]:
                    x, y = sgf_coord_to_xy(coord)
                    # Reflect across both axes for central symmetry
                    x_reflected = 18 - x
                    y_reflected = 18 - y
                    coord_reflected = xy_to_sgf_coord(x_reflected, y_reflected)
                    reflected_stones[color].append(coord_reflected)

            # Add reflected stones to prepos_new if they don't overlap with existing stones
            for color in ['b', 'w']:
                for coord in reflected_stones[color]:
                    x, y = sgf_coord_to_xy(coord)
                    if (x, y) not in existing_stones:
                        prepos_new[color].append(coord)
                        existing_stones.add((x, y))

            # Collect coordinates of reflected stones to update the exclusion area
            xs_reflected = []
            ys_reflected = []
            for color in ['b', 'w']:
                for coord in reflected_stones[color]:
                    x, y = sgf_coord_to_xy(coord)
                    xs_reflected.append(x)
                    ys_reflected.append(y)

            # Update the excluded area bounds to include both problem areas
            # Bounding box of the reflected problem area
            min_x_reflected = min(xs_reflected)
            max_x_reflected = max(xs_reflected)
            min_y_reflected = min(ys_reflected)
            max_y_reflected = max(ys_reflected)

            # Calculate distances to board edges for the reflected area
            left_distance_reflected = min_x_reflected
            right_distance_reflected = 18 - max_x_reflected
            bottom_distance_reflected = min_y_reflected
            top_distance_reflected = 18 - max_y_reflected

            # Determine sides adjacent to the edge for reflected area (distance == 0)
            if left_distance_reflected < 3:
                sides_adjacent_to_edge_reflected.add('left')
            if right_distance_reflected < 3:
                sides_adjacent_to_edge_reflected.add('right')
            if top_distance_reflected < 3:
                sides_adjacent_to_edge_reflected.add('top')
            if bottom_distance_reflected < 3:
                sides_adjacent_to_edge_reflected.add('bottom')

        else:
            # No reflection; exclusion area is based on the original problem area
            min_x_reflected = min_x
            max_x_reflected = max_x
            min_y_reflected = min_y
            max_y_reflected = max_y

        # Expand the excluded area by 1 in directions not adjacent to the edge
        exclusions_x_min_orig = 0  if 'left'  in sides_adjacent_to_edge else max(min_x - 1,0) 
        exclusions_x_max_orig = 18 if 'right' in sides_adjacent_to_edge else min(max_x + 1,18) 
        exclusions_y_min_orig = 0  if 'bottom' in sides_adjacent_to_edge else max(min_y - 1,0) 
        exclusions_y_max_orig = 18 if 'top'    in sides_adjacent_to_edge else min(max_y + 1,18) 

        exclusions_x_min_reflected = 0  if 'left'  in sides_adjacent_to_edge_reflected else max(min_x_reflected - 1,0) 
        exclusions_x_max_reflected = 18 if 'right' in sides_adjacent_to_edge_reflected else min(max_x_reflected + 1,18) 
        exclusions_y_min_reflected = 0  if 'bottom' in sides_adjacent_to_edge_reflected else max(min_y_reflected - 1,0) 
        exclusions_y_max_reflected = 18 if 'top'    in sides_adjacent_to_edge_reflected else min(max_y_reflected + 1,18) 

        # Function to check if a position is within the excluded area
        def is_in_excluded_area(x, y):
            #return (exclusions_x_min <= x <= exclusions_x_max) and (exclusions_y_min <= y <= exclusions_y_max)
            in_exclusion_original = (
                exclusions_x_min_orig <= x <= exclusions_x_max_orig and
                exclusions_y_min_orig <= y <= exclusions_y_max_orig
            )
            in_exclusion_reflected = (
                exclusions_x_min_reflected <= x <= exclusions_x_max_reflected and
                exclusions_y_min_reflected <= y <= exclusions_y_max_reflected
            )
            return in_exclusion_original or in_exclusion_reflected

        # Fill the board with black stones in the alternating pattern, avoiding the excluded area
        for x in range(19):
            if x % 2 == 0:
                y_values = range(18, -1, -2)  # Even columns: y = 18, 16, ..., 0
            else:
                y_values = range(17, -1, -2)  # Odd columns: y = 17, 15, ..., 1
            for y in y_values:
                if (x, y) not in existing_stones and not is_in_excluded_area(x, y):
                    coord = xy_to_sgf_coord(x, y)
                    prepos_new['b'].append(coord)
                    existing_stones.add((x, y))

        #增加了对称死活题，填充了黑子
        self.transformed_prepos = prepos_new
        #print(self.generate_sgf_str())

        self.ko_symmetry = True

        return prepos_new

def get_sgf(solver):
    print('original size, fill black，原始棋盘，填充黑子')
    print(solver.generate_sgf_str())
    print('original size, symmetry, fill black，原始棋盘，对称劫财，填充黑子')
    solver.symmetry_fill_black_in_empty_board()
    print(solver.generate_sgf_str())
    print('--------------------------------------------------')

    solver.swap_black_white() #黑白交换
    print('original size, bw switch, fill black，原始棋盘，填充黑子，黑白交换')
    print(solver.generate_sgf_str())
    print('original size, bw switch, symmetry, fill black，原始棋盘，填充黑子，对称劫财，黑白交换')
    solver.symmetry_fill_black_in_empty_board()
    print(solver.generate_sgf_str())
    print('--------------------------------------------------')

    #solver = GoProblemSolver(q) #缩小、旋转棋盘，审核通过的正解答案
    #print('small size，最小棋盘')
    #print(solver.generate_sgf_str())

def test():
    # Start GTP engine
    katago_cfg_filename = '/Users/zliu/go/katago/gtp_killall_do_problem.cfg'
    weight_name = 'b28' #还可以选择 b18
    engine_command = [
        "/Users/zliu/go/katago/katago-metal-1move", "gtp", 
        "-config", katago_cfg_filename,
        "-model", "/Users/zliu/go/katago/lifego_" + weight_name + ".bin.gz",
    ]
    gtp_engine = GTPEngine(engine_command)

    start_time = time.time()

    # 获取题目
    client = MongoClient()
    db = client[db_name]
    q_col = db['q']
    q = q_col.find_one({'publicid': 432})
    print(q.get('prepos'))
    solver = GoProblemSolver(q, keepsize=True)
    get_sgf(solver)

    # 设置包围情况，解题
    ret, ans = solver.solve_problem(gtp_engine)

    end_time = time.time()
    duration = end_time-start_time
    print(f'{duration:>5.2f}s')

    # Close GTP engine
    gtp_engine.close()

if __name__ == "__main__":
    test()
