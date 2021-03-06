# Based on the a star algorithm implementation from Nicholas Swift & Ryan Collingwood
# https://gist.github.com/ryancollingwood/32446307e976a11a1185a5394d6657bc
import heapq
from services.models import *
from multiprocessing import Process, Queue


def find_path(matrix, end_paths, max_path_length):
    result_queue = Queue()
    processes = []
    return_values = []
    heapq.heapify(return_values)

    start_nodes = create_nodes(Node(None, [0, 0], None), RowType.Row, matrix[0, :], end_paths, False)

    # Parallelize for each start node (top row element)
    for start_node in start_nodes:
        p = Process(target=find_path_section, args=(result_queue, matrix, end_paths, max_path_length, start_node))
        processes.append(p)
        p.start()

    for _ in processes:
        ret = result_queue.get()  # will block
        # If we already found a complete path we can terminate the remaining processes
        if ret.is_complete_end:
            for p in processes:
                p.terminate()
                p.join()
            return return_path(ret)
        heapq.heappush(return_values, ret)
    for p in processes:
        p.join()

    return return_path(heapq.heappop(return_values))

def find_path_section(result_queue, matrix, end_paths, max_path_length, start_node):
    # Initialize open list
    open_list = []
    closed_list = []

    # Heapify the open_list and closed_list
    heapq.heapify(open_list)
    heapq.heapify(closed_list)

    # Add the start nodes(top row of the matrix)
    heapq.heappush(open_list, start_node)

    outer_iterations = 0

    # Loop until we either found a complete path or there are ne more open nodes
    while len(open_list) > 0:
        outer_iterations += 1

        # Get the current node(highest priority)
        current_node = heapq.heappop(open_list)

        # Check if we found a path that solves all required sequences
        if is_completed(current_node, end_paths):
            print('Complete path found:' + return_path_code(current_node))
            current_node.is_complete_end = True
            result_queue.put(current_node)
            return

        # check if the current path is longer than the max allowed path length,
        # max_path_length is the amount of allowed nodes('buffer' in Cyberpunk).
        if len(return_path_code(current_node)) >= max_path_length * 2:
            heapq.heappush(closed_list, current_node)
            continue

        # Generate children for current node
        children = []
        next_nodes = get_nodes(current_node, matrix, end_paths)

        # if there are no further valid nodes we save the current path in case we can't find a complete path.
        if len(next_nodes) == 0:
            heapq.heappush(closed_list, current_node)
            continue

        for new_node in next_nodes:
            children.append(new_node)

        # Loop through children
        for child in children:
            # Add the child to the open list
            heapq.heappush(open_list, child)

    print(f' Path finding completed, processed {outer_iterations} nodes.')
    # could not find a complete path. Returning the best path we found.
    if len(closed_list) > 0:
        result = heapq.heappop(closed_list)
    else:
        result = None
    result_queue.put(result)


# Checks if the new node was already used int the path of the current node
def is_completed(node, end_paths):
    path = return_path_code(node)
    return all(end_path in path for end_path in end_paths)


def return_path(current_node):
    path = []
    current = current_node
    while current is not None:
        path.append(current.position)
        current = current.parent
    return path[::-1]  # Return reversed path


def return_path_code(current_node):
    path = []
    current = current_node
    while current is not None and current.code is not None:
        path.append(current.code)
        current = current.parent
    return ''.join(path[::-1])  # Return reversed path


# Returns a list of valid child nodes for a given node
def get_nodes(current_node, matrix, end_paths):
    row_type = current_node.row_type * -1  # invert the row type for child nodes
    if row_type == RowType.Row:
        row_elements = matrix[current_node.position[1], :]
    else:
        row_elements = matrix[:, current_node.position[0]]

    return create_nodes(current_node, row_type, row_elements, end_paths)


def create_nodes(current_node, row_type, row_elements, end_paths, exclude_parent=True):
    nodes = []
    i = 0
    for element in row_elements:
        # If the parent node was selected as an element of a row, the children will be taken from the column of the parent.
        if row_type == RowType.Row:
            position = [i, current_node.position[1]]
        else:
            position = [current_node.position[0], i]
        i += 1

        new_node = Node(current_node, position, element.code, row_type)

        # Null the parent node if the current node is the fake start node we have to create to feed the first row.
        if current_node.position == [0, 0] and current_node.code is None:
            new_node.parent = None
        # Ensure that we never reuse nodes.
        elif node_is_used(current_node, new_node):
            continue

        nodes.append(new_node)

        # Calculate the heuristic value for the heapq
        new_node.f = get_path_value(new_node, end_paths)

    return nodes


# Check if the new node already exists in the path of its parent.
def node_is_used(current_node, new_node):
    current = current_node
    while current is not None:
        if current == new_node:
            return True
        current = current.parent
    return False


# Heuristic function to determine the completeness of a node path
def get_path_value(node, end_paths):
    value = 0
    i = 0
    path = return_path_code(node)

    # Ensure that paths that solve one or more required sequences are valued higher than anything else
    for end_path in end_paths:
        i += 1
        if end_path in path:
            # Multiply by the position(i) in the required sequences list to value sequences with better rewards higher.
            value += 1000 * i
            continue

        # Check if the path solves a required sequence partially
        # Split the end_path by the codes tuples
        partial_paths = [end_path[i:i + 2] for i in range(0, len(end_path), 2)]
        aggregated_path = ''
        for partial_path in partial_paths:
            # Add the next code tuple to the path
            aggregated_path += partial_path
            # Check if tha current path ends with the aggregated path
            if path.endswith(aggregated_path):
                # Use the length of the matching path to ensure that paths that match more are valued higher
                value += len(aggregated_path)

    return value * -1  # invert value so min value queue can be used



