#!/usr/bin/env python3
"""Comprehensive test runner for the enterprise refactoring test suite."""

import sys
import os
import subprocess
import argparse
import time
from pathlib import Path


def run_command(command, description=""):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"Running: {description or command}")
    print(f"{'='*60}")

    start_time = time.time()
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    end_time = time.time()

    print(f"Duration: {end_time - start_time:.2f} seconds")
    print(f"Exit code: {result.returncode}")

    if result.stdout:
        print(f"\nSTDOUT:\n{result.stdout}")

    if result.stderr:
        print(f"\nSTDERR:\n{result.stderr}")

    return result


def run_unit_tests():
    """Run unit tests."""
    command = "python3 -m pytest tests/domain/ tests/application/ -v --tb=short -m 'not slow'"
    return run_command(command, "Unit Tests (Domain & Application)")


def run_infrastructure_tests():
    """Run infrastructure tests."""
    command = "python3 -m pytest tests/infrastructure/ -v --tb=short -m 'not slow'"
    return run_command(command, "Infrastructure Tests")


def run_integration_tests():
    """Run integration tests."""
    command = "python3 -m pytest tests/integration/ -v --tb=short"
    return run_command(command, "Integration Tests")


def run_e2e_tests():
    """Run end-to-end tests."""
    command = "python3 -m pytest tests/e2e/ -v --tb=short"
    return run_command(command, "End-to-End Tests")


def run_performance_tests():
    """Run performance tests."""
    command = "python3 -m pytest tests/performance/ -v --tb=short -s"
    return run_command(command, "Performance Tests")


def run_presentation_tests():
    """Run presentation layer tests."""
    command = "python3 -m pytest tests/presentation/ -v --tb=short"
    return run_command(command, "Presentation Layer Tests")


def run_all_tests():
    """Run all tests."""
    command = "python3 -m pytest tests/ -v --tb=short"
    return run_command(command, "All Tests")


def run_tests_with_coverage():
    """Run tests with coverage reporting."""
    # Install coverage if not available
    subprocess.run("pip install coverage", shell=True, capture_output=True)

    command = "python3 -m coverage run -m pytest tests/ --tb=short"
    result = run_command(command, "Tests with Coverage")

    if result.returncode == 0:
        # Generate coverage report
        coverage_result = run_command("python3 -m coverage report -m", "Coverage Report")

        # Generate HTML coverage report
        html_result = run_command("python3 -m coverage html", "HTML Coverage Report")
        if html_result.returncode == 0:
            print("\nHTML coverage report generated in htmlcov/index.html")

    return result


def run_fast_tests():
    """Run only fast tests (excluding slow/performance tests)."""
    command = "python3 -m pytest tests/ -v --tb=short -m 'not slow and not performance'"
    return run_command(command, "Fast Tests Only")


def run_specific_test_file(test_file):
    """Run a specific test file."""
    command = f"python3 -m pytest {test_file} -v --tb=short"
    return run_command(command, f"Specific Test File: {test_file}")


def check_test_environment():
    """Check if the test environment is properly set up."""
    print("Checking test environment...")

    # Check Python version
    python_version = sys.version_info
    print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")

    if python_version < (3, 8):
        print("WARNING: Python 3.8+ is recommended")

    # Check required packages
    required_packages = ["pytest", "pytest-asyncio"]
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✓ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            print(f"✗ {package} is missing")

    if missing_packages:
        print(f"\nInstalling missing packages: {', '.join(missing_packages)}")
        install_command = f"pip install {' '.join(missing_packages)}"
        subprocess.run(install_command, shell=True)

    # Check test directory structure
    test_dirs = [
        "tests/domain",
        "tests/application",
        "tests/infrastructure",
        "tests/presentation",
        "tests/integration",
        "tests/e2e",
        "tests/performance",
    ]

    for test_dir in test_dirs:
        if Path(test_dir).exists():
            test_count = len(list(Path(test_dir).rglob("test_*.py")))
            print(f"✓ {test_dir} exists ({test_count} test files)")
        else:
            print(f"✗ {test_dir} does not exist")

    print("\nEnvironment check complete.\n")


def generate_test_report():
    """Generate a comprehensive test report."""
    print("Generating comprehensive test report...")

    # Run tests with JUnit XML output
    command = "python3 -m pytest tests/ --junitxml=test_results.xml --tb=short"
    result = run_command(command, "Tests with XML Report")

    if Path("test_results.xml").exists():
        print("✓ JUnit XML report generated: test_results.xml")

    return result


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Comprehensive test runner for enterprise refactoring")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--e2e", action="store_true", help="Run end-to-end tests only")
    parser.add_argument("--performance", action="store_true", help="Run performance tests only")
    parser.add_argument("--infrastructure", action="store_true", help="Run infrastructure tests only")
    parser.add_argument("--presentation", action="store_true", help="Run presentation tests only")
    parser.add_argument("--fast", action="store_true", help="Run fast tests only (exclude slow tests)")
    parser.add_argument("--coverage", action="store_true", help="Run tests with coverage reporting")
    parser.add_argument("--report", action="store_true", help="Generate comprehensive test report")
    parser.add_argument("--check-env", action="store_true", help="Check test environment setup")
    parser.add_argument("--file", type=str, help="Run specific test file")
    parser.add_argument("--all", action="store_true", help="Run all tests")

    args = parser.parse_args()

    # Set PYTHONPATH to current directory
    os.environ["PYTHONPATH"] = os.getcwd()

    # Check environment if requested
    if args.check_env:
        check_test_environment()
        return

    # Track results
    results = []

    try:
        if args.file:
            result = run_specific_test_file(args.file)
            results.append(("Specific Test File", result.returncode))
        elif args.unit:
            result = run_unit_tests()
            results.append(("Unit Tests", result.returncode))
        elif args.integration:
            result = run_integration_tests()
            results.append(("Integration Tests", result.returncode))
        elif args.e2e:
            result = run_e2e_tests()
            results.append(("E2E Tests", result.returncode))
        elif args.performance:
            result = run_performance_tests()
            results.append(("Performance Tests", result.returncode))
        elif args.infrastructure:
            result = run_infrastructure_tests()
            results.append(("Infrastructure Tests", result.returncode))
        elif args.presentation:
            result = run_presentation_tests()
            results.append(("Presentation Tests", result.returncode))
        elif args.fast:
            result = run_fast_tests()
            results.append(("Fast Tests", result.returncode))
        elif args.coverage:
            result = run_tests_with_coverage()
            results.append(("Tests with Coverage", result.returncode))
        elif args.report:
            result = generate_test_report()
            results.append(("Test Report", result.returncode))
        elif args.all:
            result = run_all_tests()
            results.append(("All Tests", result.returncode))
        else:
            # Default: run comprehensive test suite
            print("Running comprehensive test suite...")

            # Check environment first
            check_test_environment()

            # Run different test categories
            test_suites = [
                ("Unit Tests", run_unit_tests),
                ("Infrastructure Tests", run_infrastructure_tests),
                ("Integration Tests", run_integration_tests),
                ("Presentation Tests", run_presentation_tests),
                ("E2E Tests", run_e2e_tests),
            ]

            for suite_name, suite_func in test_suites:
                result = suite_func()
                results.append((suite_name, result.returncode))

            # Run performance tests separately (they're slow)
            print("\nPerformance tests can be run separately with --performance flag")

    except KeyboardInterrupt:
        print("\n\nTest execution interrupted by user.")
        sys.exit(1)

    # Print summary
    print(f"\n{'='*60}")
    print("TEST EXECUTION SUMMARY")
    print(f"{'='*60}")

    total_suites = len(results)
    passed_suites = sum(1 for _, code in results if code == 0)
    failed_suites = total_suites - passed_suites

    for suite_name, return_code in results:
        status = "PASSED" if return_code == 0 else "FAILED"
        print(f"{suite_name}: {status}")

    print(f"\nTotal test suites: {total_suites}")
    print(f"Passed: {passed_suites}")
    print(f"Failed: {failed_suites}")

    if failed_suites > 0:
        print(f"\n❌ {failed_suites} test suite(s) failed")
        sys.exit(1)
    else:
        print(f"\n✅ All {passed_suites} test suite(s) passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
