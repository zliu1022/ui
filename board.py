#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#棋盘类（GoBoard） ：
#负责绘制棋盘，管理棋盘状态（例如，哪些位置有棋子，棋子的颜色等）。
#处理棋盘相关的操作，如落子、提子、检查棋组、判断气等。
#处理棋盘上的事件（如鼠标点击）。
#
#题目类（Problem） ：
#表示一个围棋题目，包含题目的所有信息，如初始位置、先手、难度、答案等。
#负责从数据库加载题目数据。

from pymongo import MongoClient
from pprint import pprint
from config import db_name

class GoBoard:
    def __init__(self, canvas, size=19, canvas_size=600, margin=50):
        self.canvas = canvas
        self.default_size = 19
        self.size = size
        self.canvas_size = canvas_size
        self.margin = margin
        self.default_cell_size = (canvas_size - 2 * margin) / (size - 1)
        self.cell_size = self.default_cell_size
        self.stones = [[None for _ in range(size)] for _ in range(size)]

        self.board = [[None for _ in range(2)] for _ in range(size)]
        self.coord = [[None for _ in range(4)] for _ in range(size)]
        self.corner = [None for _ in range(2)]

    def change_size(self, size=None):
        if size is not None:
            self.cell_size = self.default_cell_size * (self.default_size / size)
            self.size = size
        else:
            self.size = 19
            self.cell_size = self.default_cell_size

    def clear_board(self):
        for i in range(self.size):
            self.canvas.delete(self.board[i][0])
            self.canvas.delete(self.board[i][1])
            self.board[i][0] = None
            self.board[i][1] = None
            
            self.canvas.delete(self.coord[i][0])
            self.canvas.delete(self.coord[i][1])
            self.canvas.delete(self.coord[i][2])
            self.canvas.delete(self.coord[i][3])
            self.coord[i][0] = None
            self.coord[i][1] = None
            self.coord[i][2] = None
            self.coord[i][3] = None
        self.canvas.delete(self.corner[0])
        self.canvas.delete(self.corner[1])

    #def draw_board(self, min_dot):
    def draw_board(self):
        max_x = self.margin + (self.size - 1) * self.cell_size
        max_y = self.margin + (self.size - 1) * self.cell_size
        for i in range(self.size):
            # Vertical lines
            x = self.margin + i * self.cell_size
            self.board[i][0] = self.canvas.create_line(x, self.margin, x, max_y)
            # Horizontal lines
            y = self.margin + i * self.cell_size
            self.board[i][1] = self.canvas.create_line(self.margin, y, max_x, y)
        
        '''
        thick_size = 2
        if min_dot['name'] == 'left_top':
            self.corner[0] = self.canvas.create_line(self.margin-thick_size, max_y+thick_size, self.margin-thick_size, max_y-5*thick_size)
            self.corner[1] = self.canvas.create_line(self.margin-thick_size, max_y+thick_size, self.margin+5*thick_size, max_y+thick_size)
            self.canvas.delete(self.board[self.size-1][0])
            self.canvas.delete(self.board[0][1])
        elif min_dot['name'] == 'left_bottom':
            self.corner[0] = self.canvas.create_line(self.margin-5, self.margin-5, self.margin-5, self.margin+5)
            self.corner[1] = self.canvas.create_line(self.margin-5, self.margin-5, self.margin+5, self.margin-5)
        '''
        self._draw_coordinates()

    def _draw_coordinates(self):
        """ 绘制棋盘坐标 """
        max_x = self.margin + (self.size - 1) * self.cell_size
        max_y = self.margin + (self.size - 1) * self.cell_size
        
        columns = 'ABCDEFGHJKLMNOPQRST'
        for i in range(self.size):
            # 左侧坐标
            x_left = self.margin / 4
            y = self.margin + i * self.cell_size
            self.coord[i][0] = self.canvas.create_text(x_left, y, text=str(self.size - i))
            
            # 右侧坐标
            x_right = max_x + self.margin / 2
            self.coord[i][1] = self.canvas.create_text(x_right, y, text=str(self.size - i))
            
            # 顶部坐标
            x = self.margin + i * self.cell_size
            y_top = self.margin / 2
            self.coord[i][2] = self.canvas.create_text(x, y_top, text=columns[i])
            
            # 底部坐标
            y_bottom = max_y + 4*self.margin /5
            self.coord[i][3] = self.canvas.create_text(x, y_bottom, text=columns[i])

    def coord_to_position(self, coord):
        columns = 'abcdefghijklmnopqrs'[:self.size]
        rows    = 'srqponmlkjihgfedcba'[:self.size]
        print(columns, rows, coord, '->', end=' ')
        col_letter, row_letter = coord[1], coord[0]
        col = columns.index(col_letter)
        row = rows.index(row_letter)
        row = self.size - row - 1  # Adjust row index to match the display
        print(row, col)
        return row, col

    def position_to_coord(self, row, col):
        columns = 'abcdefghijklmnopqrst'
        row_letter = columns[self.size - row - 1]
        col_letter = columns[col]
        return col_letter + row_letter

    def draw_stone(self, row, col, color):
        x = self.margin + col * self.cell_size
        y = self.margin + row * self.cell_size
        r = self.cell_size / 2 - 2
        stone = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=color)
        return stone

    def draw_hint(self, coord):
        row, col = self.coord_to_position(coord)
        x = self.margin + col * self.cell_size
        y = self.margin + row * self.cell_size
        r = self.cell_size / 2 - 2
        hint = self.canvas.create_oval(x - r, y - r, x + r, y + r, outline='red', width=2)
        return hint

    def clear_stones(self):
        for row in range(self.size):
            for col in range(self.size):
                if self.stones[row][col] is not None:
                    self.canvas.delete(self.stones[row][col]['stone'])
                    if self.stones[row][col]['label'] is not None:
                        self.canvas.delete(self.stones[row][col]['label'])
                    self.stones[row][col] = None

    def place_preset_stones(self, prepos):
        for color, positions in prepos.items():
            for coord in positions:
                row, col = self.coord_to_position(coord)
                x = self.margin + col * self.cell_size
                y = self.margin + row * self.cell_size
                r = self.cell_size / 2 - 2
                stone_color = 'black' if color == 'b' else 'white'
                stone = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=stone_color, tags='preset_stone')
                self.stones[row][col] = {'color': stone_color, 'stone': stone, 'label': None}

class GoProblem:
    def __init__(self, problem_data=None):
        self.problem_data = problem_data or {}
        self.prepos = self.problem_data.get('prepos', {})
        self.blackfirst = self.problem_data.get('blackfirst', True)
        self.level = self.problem_data.get('level', 'N/A')
        self.answers = self.problem_data.get('answers', [])
        self.publicid = self.problem_data.get('publicid', 'N/A')
        self.ty = self.problem_data.get('qtype', 'N/A')

        self.size = self.problem_data.get('size', 19)
        if self.size != 19:
            print(self.size, self.prepos)
            new_prepos = {}
            for color in ['b', 'w']:
                positions = self.prepos.get(color, []) 
                print(positions)
                new_pos = ''
                new_pos_arr = []
                for pos_str in positions:
                    columns = 'abcdefghijklmnopqrs'
                    rows = 'srqponmlkjihgfedcba'
                    col = columns.index(pos_str[0])
                    row = rows.index(pos_str[1])
                    print(pos_str, col, row, '->', self.size-(19-col), self.size - (19-row))
                    new_pos = rows[self.size - (19-row)] + pos_str[0]
                    new_pos_arr.append(new_pos)
                new_prepos.update({color: new_pos_arr})
            print(new_prepos)
            self.prepos = new_prepos

    @staticmethod
    def load_problems_from_db(criteria):
        client = MongoClient('mongodb://localhost:27017/')
        db = client[db_name]
        collection = db['q']
        problems_cursor = collection.find(criteria)
        problems_data = list(problems_cursor)
        problems = [GoProblem(problem_data) for problem_data in problems_data]
        return problems

    def coord_to_position(self, board_size, coord):
        columns = 'abcdefghijklmnopqrs'[:board_size]
        rows    = 'srqponmlkjihgfedcba'[:board_size]
        col_letter, row_letter = coord[1], coord[0]
        col = columns.index(col_letter)
        row = rows.index(row_letter)
        row = board_size - row - 1  # Adjust row index to match the display
        return row, col

    def calculate_range(self):
        BOARD_SIZE = 19
        pre = { 
            'min_x':BOARD_SIZE,
            'min_y':BOARD_SIZE,
            'max_x':-1,
            'max_y':-1
        }   
        prepos = self.prepos
        for color in ['b', 'w']:
            positions = prepos.get(color, []) 
            for pos_str in positions:
                y, x = self.coord_to_position(BOARD_SIZE, pos_str)
                pre['max_x'] = max(pre['max_x'], x)
                pre['max_y'] = max(pre['max_y'], y)
                pre['min_x'] = min(pre['min_x'], x)
                pre['min_y'] = min(pre['min_y'], y)

        ans = { 
            'min_x':BOARD_SIZE,
            'min_y':BOARD_SIZE,
            'max_x':-1,
            'max_y':-1
        }
        # 处理 answers 字段
        answers = self.answers
        for idx, answer in enumerate(answers):
            if answer.get('ty') == 1 and answer.get('st') == 2:
                positions = answer.get('p', [])
                for pos_str in positions:
                    y, x = self.coord_to_position(BOARD_SIZE, pos_str)
                    ans['max_x'] = max(ans['max_x'], x)
                    ans['max_y'] = max(ans['max_y'], y)
                    ans['min_x'] = min(ans['min_x'], x)
                    ans['min_y'] = min(ans['min_y'], y)

        min_x = min(pre['min_x'], ans['min_x'])
        min_y = min(pre['min_y'], ans['min_y'])
        max_x = max(pre['max_x'], ans['max_x'])
        max_y = max(pre['max_y'], ans['max_y'])

        dots = [
            {'name': 'left_top',     'x': min_x, 'y': max_y},
            {'name': 'right_top',    'x': max_x, 'y': max_y},
            {'name': 'left_bottom',  'x': min_x, 'y': min_y},
            {'name': 'right_bottom', 'x': max_x, 'y': min_y}
        ]

        dot_board = [
            {'name': 'left_top',     'x': 0,            'y': BOARD_SIZE-1},
            {'name': 'right_top',    'x': BOARD_SIZE-1, 'y': BOARD_SIZE-1},
            {'name': 'left_bottom',  'x': 0,            'y': 0},
            {'name': 'right_bottom', 'x': BOARD_SIZE-1, 'y': 0}
        ]

        import math
        min_distance = 999
        min_dot = {}
        for d in dots:
            for d_board in dot_board:
                delta_x = d['x'] - d_board['x']
                delta_y = d['y'] - d_board['y']
                new_distance = delta_x * delta_x + delta_y * delta_y
                if new_distance < min_distance:
                    min_distance = new_distance
                    min_dot = {'d': d, 'd_board': d_board}
        max_distance = -1
        max_dot = {}
        for d in dots:
            delta_x = d['x'] - min_dot['d_board']['x']
            delta_y = d['y'] - min_dot['d_board']['y']
            new_distance = delta_x * delta_x + delta_y * delta_y
            if new_distance > max_distance:
                max_distance = new_distance
                max_dot = {'d': d, 'd_board': min_dot['d_board']}
        
        #最靠近角：min_dot['d_board'], 从这个角至少, atleast_boardsize+1, 棋盘
        atleast_boardsize = max(abs(max_dot['d_board']['x'] - max_dot['d']['x']), 
                                abs(max_dot['d_board']['y'] - max_dot['d']['y']))

        return atleast_boardsize+1, min_dot['d_board']