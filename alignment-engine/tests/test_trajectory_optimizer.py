import numpy as np
from core.trajectory_optimizer import TrajectoryOptimizer

def test_initialize_trajectory():
    optimizer = TrajectoryOptimizer(horizon=5, state_dim=2)
    start = np.array([0.0, 0.0])
    goal = np.array([4.0, 4.0])
    traj = optimizer._initialize_trajectory(start, goal)
    
    assert traj.shape == (5, 2)
    np.testing.assert_array_almost_equal(traj[0], start)
    np.testing.assert_array_almost_equal(traj[-1], goal)
    np.testing.assert_array_almost_equal(traj[2], np.array([2.0, 2.0]))

def test_compute_gradient_no_constraints():
    optimizer = TrajectoryOptimizer(horizon=3, state_dim=2)
    optimizer.w_goal = 1.0
    optimizer.w_smooth = 1.0
    
    # traj: [ [0,0], [1,1], [2,2] ]
    # goal: [3,3]
    traj = np.array([
        [0.0, 0.0],
        [1.0, 1.0],
        [2.0, 2.0]
    ])
    goal = np.array([3.0, 3.0])
    grad = optimizer._compute_gradient(traj, goal, [])
    
    # grad[-1] += goal_error -> [2,2] - [3,3] = [-1, -1]
    # grad[1] += 2*traj[1] - traj[0] - traj[2] -> 2*[1,1] - [0,0] - [2,2] = [0,0]
    
    assert grad.shape == (3, 2)
    np.testing.assert_array_almost_equal(grad[1], [0.0, 0.0])
    np.testing.assert_array_almost_equal(grad[-1], [-1.0, -1.0])

def test_constraint_gradient():
    optimizer = TrajectoryOptimizer(horizon=3, state_dim=2)
    traj = np.array([
        [0.0, 0.0],
        [0.5, 0.5],
        [1.0, 1.0]
    ])
    constraint = {
        "name": "obstacle_wall",
        "params": {
            "obstacle_pos": np.array([0.5, 0.5]),
            "safety_margin": 0.1
        }
    }
    grad = optimizer._constraint_gradient(traj, constraint)
    
    # at index 1, diff = [0,0], dist = 0 < 0.1
    # grad[1] -= diff / (dist + 1e-6) -> [0,0]
    assert grad.shape == (3, 2)
    np.testing.assert_array_almost_equal(grad[0], [0.0, 0.0])
    np.testing.assert_array_almost_equal(grad[1], [0.0, 0.0])
    np.testing.assert_array_almost_equal(grad[2], [0.0, 0.0])
    
    # Let's put obstacle at [0.55, 0.5]
    constraint["params"]["obstacle_pos"] = np.array([0.55, 0.5])
    grad2 = optimizer._constraint_gradient(traj, constraint)
    # diff = [-0.05, 0], dist = 0.05 < 0.1
    # grad[1] -= [-0.05, 0] / (0.05 + 1e-6) ≈ [1.0, 0.0]
    assert grad2[1][0] > 0.9

def test_solve():
    optimizer = TrajectoryOptimizer(horizon=10, state_dim=2)
    start = np.array([0.0, 0.0])
    goal = np.array([1.0, 1.0])
    
    constraint = {
        "name": "obstacle",
        "params": {
            "obstacle_pos": np.array([0.5, 0.5]),
            "safety_margin": 0.2
        }
    }
    
    traj = optimizer.solve(start, goal, [constraint])
    
    assert traj.shape == (10, 2)
    np.testing.assert_array_almost_equal(traj[0], start)
    # the last point should be close to goal
    assert np.linalg.norm(traj[-1] - goal) < 0.1
