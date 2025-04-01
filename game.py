#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#游戏逻辑类（Game） ：
#处理游戏的规则和逻辑，如判断合法性、轮到谁下棋、胜负判定等。
#管理题目加载、答案验证等功能。

import random
from board import GoProblem, GoBoard
from config import full_board_size

class GoGame:
    def __init__(self, board):
        self.board = board
        self.user_moves = []
        self.current_color = None
        self.move_number = 1
        self.hint_items = []
        self.black_captures = 0
        self.white_captures = 0
        self.problems = []
        self.current_problem = None
        self.current_problem_index = -1

    def load_problems(self):
        self.problems = GoProblem.load_problems_from_db({"status": 2, "qtype": "死活题", "level": "9K"})
        if not self.problems:
            raise Exception("No problems found")

    def load_problem(self, board, index=None):
        if index is None:
            self.current_problem_index = random.randint(0, len(self.problems) - 1)
            self.current_problem = self.problems[self.current_problem_index]
        elif index == self.current_problem_index:
            # 还是当前的题目
            pass
        else:
            self.current_problem_index = index
            self.current_problem = self.problems[index]

        # 打印题目关键信息
        print(self.current_problem.publicid, self.current_problem.size)

        # ty：1正解,2变化,3失败,4淘汰；st：1待审,2审核完成
        best_answers = [] # 审核完成的正解
        good_answers = [] # 没审核完成的正解
        for ans in self.current_problem.answers:
            if ans['ty'] == 1 and ans['st'] == 2:
                best_answers.append(ans)
            if ans['ty'] == 1 and ans['st'] == 1:
                good_answers.append(ans)
        if len(best_answers) > 0:
            self.current_problem.answers = best_answers
        elif len(good_answers) > 0:
            self.current_problem.answers = good_answers
        else:
            print('Warning: No Answer')

        self.reset_game()
        self.current_color = 'black' if self.current_problem.blackfirst else 'white'

        # 根据题目的size，改变棋盘的size，重绘棋盘
        if self.current_problem.size == full_board_size:
            # 19路棋盘，考虑绘制棋盘局部
            self.board.change_size(full_board_size)

            # Get board extent needed for the problem
            min_row, max_row, min_col, max_col = self.current_problem.get_board_extent()

            # Optionally, expand the area to include an extra row and column for better visibility
            view_distance = 2
            min_row = max(0, min_row - view_distance)
            min_col = max(0, min_col - view_distance)
            max_row = min(self.board.size - 1, max_row + view_distance)
            max_col = min(self.board.size - 1, max_col + view_distance)

            # Draw the board with the given extents
            self.board.draw_board(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col)
        else:
            # 非19路棋盘，按照具体路数绘制整个棋盘
            min_row, max_row, min_col, max_col = 0, self.current_problem.size-1, 0, self.current_problem.size-1
            self.board.change_size(self.current_problem.size)
            self.board.draw_board(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col)

        # Place preset stones
        self.board.place_preset_stones(self.current_problem.prepos)

        # Display hint for the first move
        first_move = None
        if self.current_problem.answers:
            for ans in self.current_problem.answers:
                first_move = ans['p'][0]
                self.hint_items.append(self.board.draw_hint(first_move))

        return {
            'level': self.current_problem.level,
            'color': '黑' if self.current_problem.blackfirst else '白',
            'problem_no': self.current_problem.publicid,
            'type': self.current_problem.qtype
        }

    def reset_game(self):
        self.board.clear_board()
        self.board.clear_stones()
        self.user_moves = []
        self.move_number = 1

        # Clear previous hints
        for item in self.hint_items:
            self.board.canvas.delete(item)
        self.hint_items.clear()

        self.black_captures = 0
        self.white_captures = 0

    def get_group(self, row, col):
        color = self.board.stones[row][col]['color']
        group = set()
        stack = [(row, col)]
        while stack:
            r, c = stack.pop()
            if (r, c) not in group:
                group.add((r, c))
                # Check the four neighbors
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.board.size and 0 <= nc < self.board.size:
                        if self.board.stones[nr][nc] is not None and self.board.stones[nr][nc]['color'] == color:
                            stack.append((nr, nc))
        return group

    def has_liberties(self, group):
        for r, c in group:
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.board.size and 0 <= nc < self.board.size:
                    if self.board.stones[nr][nc] is None:
                        return True
        return False

    def remove_group(self, group):
        for r, c in group:
            self.board.canvas.delete(self.board.stones[r][c]['stone'])
            if self.board.stones[r][c]['label'] is not None:
                self.board.canvas.delete(self.board.stones[r][c]['label'])
            self.board.stones[r][c] = None

    def get_expected_coords(self, move_number):
        expected_coords = set()
        for answer in self.current_problem.answers:
            if len(answer['p']) >= move_number:
                expected_coords.add(answer['p'][move_number - 1])
        return expected_coords

    def get_expected_next_coords(self, user_moves):
        expected_coords = set()
        for answer in self.current_problem.answers:
            if answer['p'][:len(user_moves)] == user_moves:
                if len(answer['p']) > len(user_moves):
                    expected_coords.add(answer['p'][len(user_moves)])
        return expected_coords

    def make_move(self, row, col):
        # Check if the position is unoccupied
        if self.board.stones[row][col] is not None:
            return 'invalid_move'

        # Get expected coordinates for the current move number
        expected_coords = self.get_expected_coords(self.move_number)
        tolerance = self.board.cell_size / 2  # Allowable distance from the correct point
        match_found = False
        coord = None

        for exp_coord in expected_coords:
            exp_row, exp_col = self.board.coord_to_position(exp_coord)
            if (exp_row, exp_col) == (row, col):
                coord = exp_coord
                match_found = True
                break

        if not match_found:
            return 'incorrect'  # 返回'错误'状态

        # Place the stone tentatively
        stone = self.board.draw_stone(row, col, self.current_color)
        label = self.board.draw_stone_number(row, col, self.current_color, self.move_number)
        self.board.stones[row][col] = {'color': self.current_color, 'stone': stone, 'label': label}

        # Perform captures
        opponent_color = 'white' if self.current_color == 'black' else 'black'
        captured_stones = 0

        # Check adjacent positions for opponent stones
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            if 0 <= nr < self.board.size and 0 <= nc < self.board.size:
                if self.board.stones[nr][nc] is not None and self.board.stones[nr][nc]['color'] == opponent_color:
                    opponent_group = self.get_group(nr, nc)
                    if not self.has_liberties(opponent_group):
                        self.remove_group(opponent_group)
                        captured_stones += len(opponent_group)
                        # Record captures
                        if self.current_color == 'black':
                            self.black_captures += len(opponent_group)
                        else:
                            self.white_captures += len(opponent_group)

        # Now check if own group has liberties
        own_group = self.get_group(row, col)
        if not self.has_liberties(own_group):
            # Invalid move: self-capture not allowed
            # Remove the placed stone
            self.board.canvas.delete(self.board.stones[row][col]['stone'])
            self.board.canvas.delete(self.board.stones[row][col]['label'])
            self.board.stones[row][col] = None
            return 'invalid_move'

        # The move is valid, proceed
        self.user_moves.append(coord)
        self.move_number += 1

        # Switch color
        self.current_color = 'white' if self.current_color == 'black' else 'black'

        # Clear previous hints
        for item in self.hint_items:
            self.board.canvas.delete(item)
        self.hint_items.clear()

        # Check if the user's sequence matches any of the answers
        matched_answers = []
        for answer in self.current_problem.answers:
            answer_moves = answer['p']
            if self.user_moves == answer_moves[:len(self.user_moves)]:
                matched_answers.append(answer)
                if len(self.user_moves) == len(answer_moves):
                    return 'correct'
                break  # Found a matching answer

        # Display hints for the next expected moves
        next_expected_coords = self.get_expected_next_coords(self.user_moves)
        for coord in next_expected_coords:
            self.hint_items.append(self.board.draw_hint(coord))

        return 'continue'  # 返回'继续'状态
