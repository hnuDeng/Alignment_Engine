"""
Test runner script.
"""

import unittest
import sys

# Add parent directory to path
sys.path.insert(0, '..')

# Import test modules
from tests.test_active_learning import *
from tests.test_data_quality import *
from tests.test_drift_detection import *


def run_all_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromModule(sys.modules['tests.test_active_learning']))
    suite.addTests(loader.loadTestsFromModule(sys.modules['tests.test_data_quality']))
    suite.addTests(loader.loadTestsFromModule(sys.modules['tests.test_drift_detection']))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
