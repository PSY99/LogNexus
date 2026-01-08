class DSU:
 """Efficient Disjoint Set Union (Union-Find) data structure"""
 def __init__(self, n):
 self.parent = list(range(n))
 def find(self, i):
 if self.parent[i] == i:
 return i
 self.parent[i] = self.find(self.parent[i])
 return self.parent[i]
 def union(self, i, j):
 root_i = self.find(i)
 root_j = self.find(j)
 if root_i != root_j:
 self.parent[root_j] = root_i