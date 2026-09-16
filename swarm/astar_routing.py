"""
A* waypoint routing -- real pathfinding over a grid, using `networkx`
(confirmed available and used to verify this, not a stand-in).

Models the flight area as a grid; obstacles (simulated no-fly cells)
block certain nodes. A* finds the shortest path around them rather
than a straight line that might cut through an obstacle. This is the
genuine A* algorithm (via networkx.astar_path, which is a real,
widely-used implementation), not a simplified imitation.

Usage: python astar_routing.py
"""

import networkx as nx


def build_grid(width: int, height: int, obstacles: set[tuple[int, int]]) -> nx.Graph:
    """4-connected grid graph, skipping obstacle cells entirely."""
    graph = nx.Graph()
    for x in range(width):
        for y in range(height):
            if (x, y) in obstacles:
                continue
            graph.add_node((x, y))
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                neighbor = (x + dx, y + dy)
                if 0 <= neighbor[0] < width and 0 <= neighbor[1] < height and neighbor not in obstacles:
                    graph.add_edge((x, y), neighbor, weight=1)
    return graph


def manhattan_heuristic(a: tuple[int, int], b: tuple[int, int]) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def find_route(width: int, height: int, start: tuple[int, int], goal: tuple[int, int],
               obstacles: set[tuple[int, int]]) -> list[tuple[int, int]]:
    """Returns the A*-shortest path from start to goal, avoiding obstacles.

    Raises networkx.NetworkXNoPath if no route exists (e.g. goal is
    walled off entirely) -- callers should handle that explicitly
    rather than assume a path always exists.
    """
    graph = build_grid(width, height, obstacles)
    return nx.astar_path(graph, start, goal, heuristic=manhattan_heuristic, weight="weight")


def _self_test():
    # A wall of obstacles directly between start and goal, with one gap.
    # A straight line would be blocked; A* must route around/through the gap.
    obstacles = {(5, y) for y in range(10) if y != 5}  # wall at x=5, gap at y=5
    path = find_route(width=10, height=10, start=(0, 0), goal=(9, 9), obstacles=obstacles)

    assert path[0] == (0, 0), "path should start at the start node"
    assert path[-1] == (9, 9), "path should end at the goal node"
    for node in path:
        assert node not in obstacles, f"BUG: path goes through obstacle at {node}"
    assert (5, 5) in path, "path should pass through the only gap in the wall (5,5)"
    print(f"PASS: A* found a {len(path)}-step path through the wall's gap, avoiding all {len(obstacles)} obstacles")

    # Sanity check: with NO obstacles, straight-ish diagonal path should be
    # exactly manhattan-distance long (18 steps + 1 for the start node = 19 nodes).
    open_path = find_route(width=10, height=10, start=(0, 0), goal=(9, 9), obstacles=set())
    expected_length = manhattan_heuristic((0, 0), (9, 9)) + 1  # +1 because path includes both endpoints
    assert len(open_path) == expected_length, (
        f"expected shortest open path to have {expected_length} nodes, got {len(open_path)}"
    )
    print(f"PASS: open grid (no obstacles) gives the optimal {len(open_path)}-node path")

    # Impossible case: goal completely walled off
    import networkx as nx_module
    sealed_obstacles = {(x, y) for x in range(10) for y in range(10)
                         if (x == 8 or y == 8) and (x, y) != (0, 0)}
    try:
        find_route(width=10, height=10, start=(0, 0), goal=(9, 9), obstacles=sealed_obstacles)
        raise AssertionError("BUG: expected NetworkXNoPath when goal is sealed off, got a path instead")
    except nx_module.NetworkXNoPath:
        print("PASS: correctly raises NetworkXNoPath when no route exists")


if __name__ == "__main__":
    _self_test()
