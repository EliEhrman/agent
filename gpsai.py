"""
Mission statement for module.
gps stands for General Problemm Solver; an 80s concept for generic AI using a basic tree-searching creation
of sub-goals. Prolog is built on this. Solve the main goal by instantiating variables then
add the components of the rule as sub-goals

In our case, the rules are learned so this is a General GPS. Moreover we can learn rules that effectively
short-cut across the branches of the tree
"""
from __future__ import print_function
import numpy as np

class cl_gpsai_mgr(object):
	def __init__(self):
		pass

	def set_mgrs(self, mpdb_mgr):
		self.__mpdb_mgr = mpdb_mgr

	def set_player_goal(self, player_name, goal_stmt, rules_mgr):
		pass

