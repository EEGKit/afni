from argparse import Namespace
from collections import namedtuple
import pathlib
from pathlib import Path
from unittest.mock import Mock, MagicMock
import importlib
import os
import pytest
import runpy
import shlex
import shutil
import subprocess
import subprocess as sp
import sys
import tempfile
import io
from contextlib import redirect_stdout
import contextlib

docker = pytest.importorskip("docker", reason="python docker is not installed")

# import afni_test_utils as atu
from afni_test_utils import run_tests_func
from afni_test_utils import run_tests_examples
from afni_test_utils import container_execution as ce
from afni_test_utils import minimal_funcs_for_run_tests_cli as minfuncs
import afnipy

# import the whole package for mocking purposes
import afni_test_utils

TESTS_DIR = Path(__file__).parent.parent
SCRIPT = TESTS_DIR.joinpath("run_afni_tests.py")
# The default args to pytest will likely change with updates
DEFAULT_ARGS = "scripts --tb=no --no-summary --show-capture=no"
PYTEST_COV_FLAGS = "--cov=targets_built --cov-report xml:$PWD/coverage.xml"
RETCODE_0 = Mock()
RETCODE_0.returncode = 0
RETCODE_0.stdout = b""
RETCODE_0.stderr = b""


@pytest.fixture()
def mocked_script(monkeypatch):
    temp_dir = tempfile.mkdtemp()
    exe_dir = Path(temp_dir) / "tests"
    exe_dir.mkdir()
    monkeypatch.syspath_prepend(exe_dir)

    script = Path(
        tempfile.mkstemp(dir=exe_dir, prefix="script_test_", suffix=".py")[-1]
    )
    return script


@pytest.fixture()
def mocked_abin():
    """
    Fixture to supply 'mocked_abin', a directory containing trivial
    executables called 3dinfo and align_epi_anat.py and afnipy/afni_base.py (an
    importable python module)
    """
    temp_dir = tempfile.mkdtemp()
    abin_dir = Path(temp_dir) / "abin"
    abin_dir.mkdir()

    (abin_dir / "3dinfo").touch(mode=0o777)
    (abin_dir / "libmri.so").touch(mode=0o444)
    (abin_dir / "3dinfo").write_text("#!/usr/bin/env bash\necho success")
    (abin_dir / "align_epi_anat.py").touch(mode=0o777)
    (abin_dir / "align_epi_anat.py").write_text("#!/usr/bin/env bash\necho success")
    (abin_dir / "afnipy").mkdir()
    (abin_dir / "afnipy/afni_base.py").touch()
    (abin_dir / "afnipy/__init__.py").touch()
    return abin_dir


def create_fake_installation_hierarchical():
    """
    Creates a fake installation directory containing trivial executables
    called 3dinfo and align_epi_anat.py and afnipy/afni_base.py (an importable
    python module) along with libmri in the appropriate organization defined
    by the GNU installation guidelines. To use this you should add the
    fake_site_packages directory to sys.path to simulate the afnipy package
    being installed into the current interpreter.
    """
    temp_dir = tempfile.mkdtemp()
    # Create an installation directory
    instd = Path(temp_dir) / "abin_hierarchical"
    instd.mkdir()
    bindir = instd / "bin"
    bindir.mkdir()

    (bindir / "3dinfo").touch(mode=0o777)
    (bindir / "3dinfo").write_text("#!/usr/bin/env bash\necho success")
    (instd / "lib/").mkdir()
    (instd / "lib/libmri.so").touch(mode=0o444)
    (instd / "fake_site_packages").mkdir()
    (instd / "fake_site_packages/align_epi_anat.py").touch(mode=0o777)
    (instd / "fake_site_packages/align_epi_anat.py").write_text(
        "#!/usr/bin/env bash\necho success"
    )
    (instd / "fake_site_packages/afnipy").mkdir()
    (instd / "fake_site_packages/afnipy/afni_base.py").touch()
    (instd / "fake_site_packages/afnipy/__init__.py").touch()
    return instd


@pytest.fixture()
def sp_with_successful_execution():

    RUN_WITH_0 = Mock()
    RUN_WITH_0.run.return_value = RETCODE_0
    RUN_WITH_0.check_output.return_value = b""
    return RUN_WITH_0


def run_main_func(script_obj, sys_exit):
    if sys_exit:
        with pytest.raises(SystemExit) as err:
            script_obj.main()
        assert err.typename == "SystemExit"
        assert err.value.code == 0
    else:
        script_obj.main()


def run_script_and_check_imports(
    script_path,
    argslist,
    expected,
    not_expected,
    monkeypatch,
    sys_exit=True,
    no_output=True,
):
    """
    This needs to be used with the mocked_script fixture.

    This is very hacky. It is testing something hacky though. The overall goal
    is to try to only import dependencies of the core testing script as
    needed. In order for that behavior to be robust it must be tested here.

    I tried runpy as a way to execute the script but it didn't work (it was
    modifying sys.argv in a way I could not decipher).

    sys.argv is temporarily modified to test different "user" arguments during
    the import and subsequent execution. Subsequently we check if the
    appropriate imports have occurred.
    """
    with monkeypatch.context() as m:
        m.setattr(sys, "argv", [script_path.name, *argslist])

        script = importlib.import_module(script_path.stem)

        for func_or_mod in not_expected:
            if func_or_mod:
                assert not getattr(script, func_or_mod, None)
        for func_or_mod in expected:
            if func_or_mod:
                assert getattr(script, func_or_mod, None)

        if no_output:
            with contextlib.redirect_stdout(io.StringIO()):
                run_main_func(script, sys_exit)
        else:
            run_main_func(script, sys_exit)


def test_check_git_config(
    monkeypatch,
):
    mocked_run_output = Mock()
    mocked_run_output.stdout = b""
    mocked_sp = Mock()
    mocked_sp.run.return_value = mocked_run_output
    mocked_sp.check_output.return_value = b"a_value"

    monkeypatch.setattr(
        afni_test_utils.minimal_funcs_for_run_tests_cli,
        "sp",
        mocked_sp,
    )
    monkeypatch.setattr(
        afni_test_utils.minimal_funcs_for_run_tests_cli,
        "is_containerized",
        Mock(return_value=False),
    )
    # if credentials are unset should raise error
    with monkeypatch.context() as m:
        m.setattr(os, "environ", {})
        with pytest.raises(EnvironmentError):
            minfuncs.check_git_config()

    # env variables should be sufficient
    with monkeypatch.context() as m:
        m.setattr(
            os,
            "environ",
            {"GIT_AUTHOR_NAME": "user", "GIT_AUTHOR_EMAIL": "user@mail.com"},
        )
        minfuncs.check_git_config()

    # credentials should be sufficient
    with monkeypatch.context() as m:
        m.setattr(os, "environ", {})
        # simulate existing credentials
        mocked_run_output.stdout = b"a_value"
        minfuncs.check_git_config()


def test_check_git_config_containerized(sp_with_successful_execution, monkeypatch):
    def existing_dockerenv(*args, **kwargs):
        """
        local function to help pretend this test is containerized
        """
        if "/.dockerenv" in args:
            mocked_path = Mock()
            mocked_path.exists.return_value = True
            return mocked_path
        else:
            return Path(*args, **kwargs)

    monkeypatch.setattr(minfuncs, "sp", sp_with_successful_execution)
    # Pretend this is running in a container
    monkeypatch.setattr(
        minfuncs,
        "Path",
        existing_dockerenv,
    )
    # if containerized local setting might still return credentials

    # if containerized env vars should still work unless they were not sent in

    # if containerized if all else fails set a default

    # if credentials are unset should be fine if containerized and set to a default
    with monkeypatch.context() as m:
        m.setattr(os, "environ", {})
        # sp_with_successful_execution.check_output.return_value = b'a_value'
        u, e = minfuncs.check_git_config()
        sp_with_successful_execution.check_output.assert_any_call(
            "git config --global user.name 'AFNI CircleCI User'",
            shell=True,
        )
        sp_with_successful_execution.check_output.assert_any_call(
            "git config --global user.email 'johnleenimh+circlecigitconfig@gmail.com'",
            shell=True,
        )
        assert u == "AFNI CircleCI User"
        assert e == "johnleenimh+circlecigitconfig@gmail.com"

    # env variables should set the value if not set on  the system
    with monkeypatch.context() as m:
        m.setattr(
            os,
            "environ",
            {"GIT_AUTHOR_NAME": "user", "GIT_AUTHOR_EMAIL": "user@mail.com"},
        )
        # credentials should be sufficient, and overwrite env vars (they
        # can leak into container via local config in mounted source)
        credential_returned = Mock(**{"stdout": b"a_value"})
        sp_with_successful_execution.run.return_value = credential_returned
        gituser, gitemail = minfuncs.check_git_config()
        assert gituser == "a_value"
        assert gitemail == "a_value"

        # If missing credentials, fall back to vars
        empty_run = Mock(**{"stdout": b"", "returncode": 1})
        sp_with_successful_execution.run.return_value = empty_run
        gituser, gitemail = minfuncs.check_git_config()
        assert gituser == "user"
        assert gitemail == "user@mail.com"


def test_run_containerized(monkeypatch):
    container = Mock(
        **{
            "logs.return_value": [b"success"],
            "wait.return_value": {'StatusCode':False},
        })
    client = Mock(**{"containers": Mock(**{"run.return_value": container})})
    mocked_docker = Mock(**{"from_env.return_value": client})
    monkeypatch.setattr(ce, "docker", mocked_docker)
    monkeypatch.setattr(ce, "get_docker_image", Mock())
    monkeypatch.setenv("GIT_AUTHOR_NAME", "user")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "user@mail.com")
    # Calling with coverage=True should result in --coverage being in the
    # docker run call
    ce.run_containerized(
        TESTS_DIR,
        **{
            "image_name": "afni/afni_cmake_build",
            "only_use_local": True,
            "coverage": True,
        },
    )
    run_calls = client.containers.run.call_args_list
    assert "--coverage" in run_calls[0][0][1]


@pytest.mark.skipif(
    minfuncs.is_containerized(),
    reason=("This test is not run inside the container."),
)
def test_run_containerized_fails_with_unknown_image():
    # The image needs to exist locally with only_use_local
    with pytest.raises(ValueError):
        ce.run_containerized(
            TESTS_DIR,
            **{
                "image_name": "unknown_image",
                "only_use_local": True,
            },
        )


@pytest.mark.parametrize(
    "help_option",
    [
        *"-h --help -help examples --installation-help".split(),
    ],
)
def test_run_tests_help_works(mocked_script, monkeypatch, help_option):
    """
    Various calls of run_afni_tests.py should have no dependencies to
    correctly execute: basically help can be displayed without dependencies
    installed
    """
    not_expected = "datalad docker pytest afnipy run_tests".split()
    expected = ""
    argslist = [help_option]

    # Write run_afni_tests.py to an executable/importable path
    mocked_script.write_text(SCRIPT.read_text())

    run_script_and_check_imports(
        mocked_script, argslist, expected, not_expected, monkeypatch
    )


@pytest.mark.parametrize(
    "params",
    [
        {
            "test_case": "no additional args",
            "argslist": ["local"],
            "expected": [""],
            "not_expected": ["local"],
        },
        {
            "test_case": "--abin should mean afnipy is not imported",
            "argslist": f"--abin {tempfile.mkdtemp()} local".split(),
            "expected": [""],
            "not_expected": ["afnipy", "docker"],
        },
        {
            "test_case": "--abin could be passed with equals",
            "argslist": f"--abin={tempfile.mkdtemp()} local".split(),
            "expected": [""],
            "not_expected": ["afnipy", "docker"],
        },
        {
            "test_case": "--build-dir",
            "argslist": f"--build-dir={tempfile.mkdtemp()} local".split(),
            "expected": ["afnipy"],
            "not_expected": ["docker"],
        },
    ],
)
def test_run_tests_local_subparsers_works(monkeypatch, params, mocked_script):
    """
    This runs some basic checks for the command line parsing of the
    run_afni_test.py tool. There is a bit of complicated stuff going on to
    make sure only the subparsing behavior is tested (as opposed to actually
    running the test suite each time!). Roughly speaking, this magic consists
    of mocking the run_tests function and writing the contents of
    run_afni_test.py to a test specific path that can be imported
    from/executed for each test parameter in an isolated manner.
    """
    monkeypatch.setattr(afni_test_utils.run_tests_func, "run_tests", RETCODE_0)
    # env check not needed
    monkeypatch.setattr(
        afni_test_utils.minimal_funcs_for_run_tests_cli,
        "modify_path_and_env_if_not_using_cmake",
        lambda *args, **kwargs: None,
    )

    # Write run_afni_tests.py to an executable/importable path
    mocked_script.write_text(SCRIPT.read_text())
    run_script_and_check_imports(
        mocked_script,
        params["argslist"],
        params["expected"],
        params["not_expected"],
        monkeypatch,
        sys_exit=False,
    )


@pytest.mark.parametrize(
    "argslist",
    [
        "container --source-mode=host".split(),
        ["container"],
    ],
)
def test_run_tests_container_subparsers_works(monkeypatch, argslist, mocked_script):
    """
    This runs some basic checks for the command line parsing of the
    run_afni_test.py tool when the container option is used. There is a bit of
    complicated stuff going on to make sure only the subparsing behavior is
    tested (as opposed to actually running the test suite each time!). Roughly
    speaking, this magic consists of mocking the run_containerized function
    and writing the contents of run_afni_test.py to a test specific path that
    can be imported from/executed for each test parameter in an isolated
    manner.
    """
    mocked_run_containerized = RETCODE_0
    monkeypatch.setattr(
        afni_test_utils.container_execution,
        "run_containerized",
        mocked_run_containerized,
    )
    not_expected = "datalad docker pytest afnipy run_tests".split()
    expected = ""

    # Write run_afni_tests.py to an executable/importable path
    mocked_script.write_text(SCRIPT.read_text())

    run_script_and_check_imports(
        mocked_script, argslist, expected, not_expected, monkeypatch, sys_exit=False
    )


@pytest.mark.parametrize(
    "params",
    [
        {
            "test_case": "default",
            "args_in": {},
            "expected_call_template": "{sys.executable} -m pytest {DEFAULT_ARGS}",
        },
        {
            "test_case": "with_coverage",
            "args_in": {"coverage": True, "build_dir": tempfile.mkdtemp()},
            "expected_call_template": (
                "cd {params['args_in']['build_dir']};"
                "cmake -GNinja {TESTS_DIR.parent};"
                "ARGS='{DEFAULT_ARGS} {PYTEST_COV_FLAGS}' "
                "ninja pytest"
            ),
        },
    ],
)
def test_run_tests_with_args(monkeypatch, params, sp_with_successful_execution):
    template = params["expected_call_template"]
    # All substituted variables should be defined in this scope
    expected_call = eval(f'f"""{template}"""')

    # Should not fail with missing credentials
    monkeypatch.setenv("GIT_AUTHOR_NAME", "user")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "user@mail.com")

    # Create a mock so that subprocess.run calls return 0 exit status
    monkeypatch.setattr(
        afni_test_utils.run_tests_func,
        "subprocess",
        sp_with_successful_execution,
    )
    # mock os.environ so that race conditions do not occur during parallel testing
    monkeypatch.setattr(
        os,
        "environ",
        os.environ.copy(),
    )
    with pytest.raises(SystemExit) as err:
        afni_test_utils.run_tests_func.run_tests(TESTS_DIR, **params["args_in"])
        assert err.typename == "SystemExit"
        assert err.value.code == 0
    sp_with_successful_execution.run.assert_called_with(expected_call, shell=True)


def test_handling_of_binary_locations_and_afnipy_when_cmake_build_is_used(
    monkeypatch, mocked_abin
):
    """
    Testing situation 1. of modify_path_and_env_if_not_using_cmake: the cmake
    manages the details and masks any system state. afnipy should already be
    installed into the python interpretter when executing tests in this mode.
    All scripts/binaries are prepended to the path on the fly.

    Might want to consider having  a text file during installation that points
    to the appropariate interpreter and an accurate error of such a missing
    interpreter is raised? This would solve issues with the wrong environment
    being activated.
    """

    # create a mock import to control whether afnipy is "imported correctly" or not
    mocked_import = Mock()
    mocked_import.__file__ = "mocked_path_for_imported_module"
    # afnipy may or may not be importable in this situation, lets begin with
    # not importable
    mocked_import_module = MagicMock(
        side_effect=ImportError, return_value=mocked_import
    )
    with monkeypatch.context() as m:
        # Create mocks so that os.environ and importing simulate situation 1. and
        # can be set and modified safely
        m.setattr(run_tests_func.importlib, "import_module", mocked_import_module)

        with pytest.raises(EnvironmentError):
            # Run function to check no error is raised without afnipy
            minfuncs.modify_path_and_env_if_not_using_cmake(
                os.getcwd(),
                build_dir="a_directory",
            )

        mocked_import_module.side_effect = None
        # should work when afnipy is importable
        minfuncs.modify_path_and_env_if_not_using_cmake(
            os.getcwd(),
            build_dir="a_directory",
        )


def test_handling_of_binary_locations_and_afnipy_for_a_heirarchical_installation(
    monkeypatch,
):
    """
    Testing situation 2. of modify_path_and_env_if_not_using_cmake: cmake
    installation. AFNI binaries are on the PATH but shared object libraries
    are in ../lib and afnipy has been installed into the python interpreter.
    """
    # Create a directory that has the GNU installation pattern
    fake_install = create_fake_installation_hierarchical()
    fake_bin = str(fake_install / "bin")

    # create a mock import to control whether afnipy is "imported correctly"
    # or not
    mocked_import = Mock()
    mocked_import.__file__ = "mocked_path_for_imported_module"
    mocked_import_module = MagicMock(return_value=mocked_import)
    with monkeypatch.context() as m:
        # Create mocks so that os.environ and importing situation 2. and
        # can be set/modified safely
        m.setattr(run_tests_func.importlib, "import_module", mocked_import_module)
        filtered_path = minfuncs.filter_afni_from_path()
        m.setattr(
            os,
            "environ",
            {"PATH": f"{fake_bin}:{filtered_path}"},
        )
        m.setattr(sys, "path", sys.path.copy())
        # make 3dinfo available
        sys.path.insert(0, fake_bin)
        # make fake afnipy importable (via reload)
        sys.path.insert(0, str(fake_install / "fake_site_packages"))

        # With the current mocking "3dinfo" should be on the path and afnipy
        # should be importable
        assert sp.run("3dinfo")
        assert Path(shutil.which("3dinfo")).parent == Path(fake_bin)
        assert importlib.reload(afnipy)
        assert Path(afnipy.__file__).parent.parent.parent == fake_install

        # Run function to check that no error is raised spuriously
        minfuncs.modify_path_and_env_if_not_using_cmake(os.getcwd())


def test_handling_of_binary_locations_and_afnipy_for_default_run(
    monkeypatch, mocked_abin
):
    """
    Testing situation 3. of modify_path_and_env_if_not_using_cmake: typical
    abin installation. AFNI binaries are no the PATH. afnipy should not be
    importable until after function is executed.

    By default when the test suite is run, it is expected that abin is on the
    PATH (the standard flat directory structure of the make build distribution
    is being used). This means that python binaries should be in the same
    directory as c binaries and on the PATH. Python binaries in abin have no
    problem importing from afnipy since it sits in the same directory but
    python code outside of this will (including the test suite code). The
    python search path and os.environ are modified to remedy any issues caused
    by this for the test suite code. If afnipy is installed in this situation
    an error should be raised to prompt for its removal: this state is
    unsupported because it is ambiguous as to which version of python code
    will be used in all the various calling patterns that can occur
    (subprocess calls, subprocess calls to shell scripts that attempt to
    execute python binaries, imports of python modules etc.)
    """

    # create a mock import to control whether afnipy is "imported correctly"
    # or not
    mocked_import = Mock()
    mocked_import.__file__ = "mocked_path_for_imported_module"
    mocked_import_module = MagicMock(
        side_effect=ImportError, return_value=mocked_import
    )
    with monkeypatch.context() as m:
        # Create mocks so that os.environ and importing situation 3. and
        # can be set and set/modified safely
        m.setattr(run_tests_func.importlib, "import_module", mocked_import_module)

        filtered_path = minfuncs.filter_afni_from_path()
        m.setattr(
            os,
            "environ",
            {"PATH": f"{mocked_abin}:{filtered_path}"},
        )

        # With the current mocking "3dinfo" should be on the path,
        sp.run("3dinfo")

        # Run function to check that a setup for a testing session correctly
        # modifies the environment and sys.path
        minfuncs.modify_path_and_env_if_not_using_cmake(
            os.getcwd(),
        )

        # The current python interpreter should now be able to import afnipy
        # without issue (and it should be imported from the mocked abin)
        mocked_afnipy = importlib.reload(afnipy)
        assert Path(mocked_afnipy.__file__).parent.parent == mocked_abin

        # If import afnipy does not fail, an error should be raised
        mocked_import_module.side_effect = None
        with pytest.raises(EnvironmentError):
            minfuncs.modify_path_and_env_if_not_using_cmake(
                os.getcwd(),
            )


def test_handling_of_binary_locations_and_afnipy_when_abin_as_flag(
    monkeypatch, mocked_abin
):
    """
    Testing situation 4. of modify_path_and_env_if_not_using_cmake: flat
    directory installation but not necessarily on PATH (passed as a flag).
    afnipy should not be importable until after function is executed.
    """

    # create a mock import to control whether afnipy is "imported correctly" or not
    mocked_import = Mock()
    mocked_import.__file__ = "mocked_path_for_imported_module"
    mocked_import_module = MagicMock(
        side_effect=ImportError, return_value=mocked_import
    )
    with monkeypatch.context() as m:
        # Create mocks so that os.environ and importing simulate situation 4. and
        # can be set and modified safely
        m.setattr(run_tests_func.importlib, "import_module", mocked_import_module)

        filtered_path = minfuncs.filter_afni_from_path()
        m.setattr(
            os,
            "environ",
            {"PATH": f"{filtered_path}"},
        )

        # With the current mocking "3dinfo" should not be on the path. If this
        # does fail in finding 3dinfo you can add the afni installation
        # directory that is found on the path to 'abin_patterns' in
        # minfuncs.filter_afni_from_path.
        with pytest.raises(FileNotFoundError):
            sp.run("3dinfo")

        # Run function to check that a setup for a testing session correctly
        # modifies the environment and sys.path
        minfuncs.modify_path_and_env_if_not_using_cmake(
            os.getcwd(),
            abin=str(mocked_abin),
        )
        # The fake binary should now be able to executed with no error
        sp.run("3dinfo")

        # The current python interpreter should now be able to import afnipy
        # without issue (and it should be imported from the mocked abin)
        mocked_afnipy = importlib.reload(afnipy)
        assert Path(mocked_afnipy.__file__).parent.parent == mocked_abin

        # If the import of afnipy does not fail when running the function in
        # this context (abin flag is passed but afnipy is importable), an
        # error should be raised
        mocked_import_module.side_effect = None
        with pytest.raises(EnvironmentError):
            minfuncs.modify_path_and_env_if_not_using_cmake(
                os.getcwd(),
                abin=str(mocked_abin),
            )


def test_examples_parse_correctly(monkeypatch):
    # dir_path needs to be mocked to prevent errors being raise for
    # non-existent paths
    monkeypatch.setattr(
        afni_test_utils.minimal_funcs_for_run_tests_cli,
        "dir_path",
        lambda x: str(Path(x).expanduser()),
    )
    stdout_ = sys.stdout  # Keep track of the previous value.
    for name, example in run_tests_examples.examples.items():
        # Generate the 'sys.argv' for the example
        arg_list = shlex.split(example.splitlines()[-1])[1:]
        # Execute the script so that it can be run.
        res = runpy.run_path(str(SCRIPT))

        res["sys"].argv = [SCRIPT.name, *arg_list]
        res["main"].__globals__["run_tests"] = Mock(side_effect=SystemExit(0))
        res["main"].__globals__["run_containerized"] = Mock(side_effect=SystemExit(0))
        res["main"].__globals__[
            "minfuncs"
        ].modify_path_and_env_if_not_using_cmake = lambda *args, **kwargs: None
        with pytest.raises(SystemExit) as err:
            # Run main function while redirecting to /dev/null
            sys.stdout = open(os.devnull, "w")
            res["main"]()
            sys.stdout = stdout_  # restore the previous stdout.

        assert err.typename == "SystemExit"
        assert err.value.code == 0

        if "local" in arg_list:
            res["main"].__globals__["run_tests"].assert_called_once()
        elif "container" in arg_list:
            res["main"].__globals__["run_containerized"].assert_called_once()

    sys.stdout = stdout_  # restore the previous stdout.


@pytest.mark.parametrize(
    "params",
    [
        # basic usage
        {},
        # test-data-volume is a valid value for source_mode
        {
            "image_name": "an_image",
            "only_use_local": False,
            "source_mode": "test-data-volume",
        },
        # Build dir outside of source should work
        {
            "image_name": "an_image",
            "only_use_local": False,
            "source_mode": "host",
            "build_dir": tempfile.mkdtemp(),
        },
    ],
)
def test_check_user_container_args(params):
    ce.check_user_container_args(TESTS_DIR, **params)


@pytest.mark.parametrize(
    "params",
    [
        # Value error should be raised if build is in source
        {
            "image_name": "an_image",
            "only_use_local": False,
            "source_mode": "host",
            "build_dir": str(TESTS_DIR),
        },
        # reuse-build conflicts with build-dir because reuse implies container build dir
        {
            "image_name": "an_image",
            "only_use_local": False,
            "source_mode": "host",
            "build_dir": tempfile.mkdtemp(),
            "reuse_build": True,
        },
        # test-code mounting conflicts with build-dir and reuse-build because test-code implies
        # using installed version of afni
        {
            "image_name": "an_image",
            "only_use_local": False,
            "source_mode": "test-code",
            "build_dir": tempfile.mkdtemp(),
        },
        # image needs to exist
        {
            "image_name": "an_image",
            "only_use_local": False,
            "source_mode": "test-code",
            "reuse_build": True,
        },
    ],
)
def test_check_user_container_args_failures(params):
    with pytest.raises(ValueError):
        ce.check_user_container_args(TESTS_DIR, **params)


def test_check_user_container_args_with_root(monkeypatch):
    # this contains a bit of a hack because I couldn't figure out how to patch
    # minfuncs.os on a test specific basis

    with monkeypatch.context() as m:

        def mock_uid():
            return "0"

        m.setattr(os, "getuid", mock_uid)

        with pytest.raises(ValueError):
            ce.check_user_container_args(
                TESTS_DIR,
                image_name="afni/afni_cmake_build",
                only_use_local=False,
                source_mode="host",
            )
        with pytest.raises(ValueError):
            ce.check_user_container_args(
                TESTS_DIR,
                image_name="afni/afni_cmake_build",
                only_use_local=False,
                build_dir=tempfile.mkdtemp(),
            )


def test_get_test_cmd_args():
    cmd_args = minfuncs.get_test_cmd_args(overwrite_args="")
    assert not cmd_args

    # Check default commands
    cmd_args = minfuncs.get_test_cmd_args()
    assert cmd_args == ["scripts", "--tb=no", "--no-summary", "--show-capture=no"]

    cmd_args = minfuncs.get_test_cmd_args(verbose=3)
    assert "--showlocals" in cmd_args


def test_configure_parallelism_parallel(monkeypatch):
    # define a mock sp.check_output for testing purposes
    def mocked_output(*args, **kwargs):
        """
        local function to help pretend pytest is run with pytest-parallel
        available (regardless of its installation status)
        """
        if any("pytest" in a for a in args):
            return bytes("pytest-parallel", "utf-8")
        else:
            proc = sp.run(*args, **kwargs, stdout=sp.PIPE)
            if proc.returncode:
                raise ValueError(
                    "This command should not have failed. This is testing something else."
                )
            return proc.stdout

    # When the user has requested to run the tests in parallel, the --workers
    # option is used for the pytest call and omp var set to 1
    monkeypatch.setattr(minfuncs.sp, "check_output", mocked_output)
    with monkeypatch.context() as m:
        m.setattr(os, "environ", {})
        assert not os.environ.get("OMP_NUM_THREADS")
        # check use_all_cores works with current plugin
        cmd_args = minfuncs.configure_parallelism([], use_all_cores=True)
        flag_in_args = "--workers" in cmd_args
        assert flag_in_args
        assert os.environ["OMP_NUM_THREADS"] == "1"


def test_configure_parallelism_parallel_with_missing_plugin(monkeypatch):
    # error should be raised if pytest-parallel is not installed
    def mocked_output(*args, **kwargs):
        """
        local function to help pretend pytest is run with different plugin
        configurations
        """
        if any("pytest" in a for a in args):
            return bytes("no plugin name is contained in this string", "utf-8")
        else:
            proc = sp.run(*args, **kwargs, stdout=sp.PIPE)
            if proc.returncode:
                raise ValueError(
                    "This command should not have failed. This is testing something else."
                )
            return proc.stdout

    monkeypatch.setattr(minfuncs.sp, "check_output", mocked_output)
    # check use_all_cores works with current plugin
    with pytest.raises(EnvironmentError):
        cmd_args = minfuncs.configure_parallelism([], use_all_cores=True)


def test_configure_parallelism_serial(monkeypatch):
    # for serial testing workers option not passed and OMP var set
    with monkeypatch.context() as m:
        m.setattr(os, "environ", {})
        assert not os.environ.get("OMP_NUM_THREADS")
        cmd_args = minfuncs.configure_parallelism([], use_all_cores=False)
        assert "-n" not in cmd_args
        assert os.environ.get("OMP_NUM_THREADS")


def test_configure_for_coverage(monkeypatch):
    cmd_args = ["scripts"]
    # Coverage should fail without a build directory
    with pytest.raises(ValueError):
        out_args = minfuncs.configure_for_coverage(cmd_args, coverage=True)

    with monkeypatch.context() as m:
        m.setattr(os, "environ", os.environ.copy())
        if "CFLAGS" in os.environ:
            del os.environ["CFLAGS"]
        if "LDFLAGS" in os.environ:
            del os.environ["LDFLAGS"]
        if "CXXFLAGS" in os.environ:
            del os.environ["CXXFLAGS"]

        # Check vars are not inappropriately set when not requested
        out_args = minfuncs.configure_for_coverage(
            cmd_args, coverage=False, build_dir="something"
        )
        assert not any([os.environ.get(x) for x in "CFLAGS CXXFLAGS LDFLAGS".split()])

        # Check coverage flags are added when requested
        out_args = minfuncs.configure_for_coverage(
            cmd_args, coverage=True, build_dir="something"
        )
        assert all(x in out_args for x in PYTEST_COV_FLAGS.split())
        assert (
            os.environ.get("CXXFLAGS")
            == "-g -O0 -Wall -W -Wshadow -Wunused-variable -Wunused-parameter -Wunused-function -Wunused -Wno-system-headers -Wno-deprecated -Woverloaded-virtual -Wwrite-strings -fprofile-arcs -ftest-coverage"
        )
        assert (
            os.environ.get("CFLAGS") == "-g -O0 -Wall -W -fprofile-arcs -ftest-coverage"
        )
        assert os.environ.get("LDFLAGS") == "-fprofile-arcs -ftest-coverage"


def test_generate_cmake_command_as_required():
    adict = {"build_dir": tempfile.mkdtemp()}
    output = minfuncs.generate_cmake_command_as_required(TESTS_DIR, adict)
    assert "cmake -GNinja" in output


def test_unparse_args_for_container():
    user_args = {}
    expected = """ local"""
    converted = ce.unparse_args_for_container(TESTS_DIR, **user_args)
    assert converted == expected

    user_args = {
        "build_dir": "/saved/afni/build",
        "debug": True,
        "extra_args": None,
        "ignore_dirty_data": False,
        "image_name": "afni/afni_cmake_build",
        "source_mode": "host",
        "only_use_local": True,
        "use_all_cores": False,
        "coverage": True,
        "verbose": False,
    }
    expected = """ --build-dir=/opt/afni/build --debug --coverage local"""
    converted = ce.unparse_args_for_container(TESTS_DIR, **user_args)
    assert converted == expected

    user_args = {
        "debug": False,
        "extra_args": "-k hello --trace",
        "use_all_cores": False,
        "coverage": True,
        "verbose": False,
    }
    expected = """ --extra-args="-k hello --trace" --coverage local"""
    converted = ce.unparse_args_for_container(TESTS_DIR, **user_args)
    assert converted == expected

    # underscores should be converted for any kwargs passed through (when
    # their value is True at least)
    user_args = {"arbitrary_kwarg_with_underscores": True}

    converted = ce.unparse_args_for_container(TESTS_DIR, **user_args)
    assert "--arbitrary-kwarg-with-underscores local" in converted

    # --reuse-build should
    user_args = {"reuse_build": True}

    converted = ce.unparse_args_for_container(TESTS_DIR, **user_args)
    assert "--build-dir=/opt/afni/build" in converted


def test_setup_docker_env_and_vol_settings(monkeypatch):
    # Should not fail with missing credentials
    monkeypatch.setenv("GIT_AUTHOR_NAME", "user")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "user@mail.com")

    # basic usage
    ce.setup_docker_env_and_vol_settings(
        TESTS_DIR,
    )

    # Confirm source directory is mounted
    source_dir, *_ = ce.get_path_strs_for_mounting(TESTS_DIR)
    docker_kwargs = ce.setup_docker_env_and_vol_settings(
        TESTS_DIR,
        **{"source_mode": "host"},
    )
    assert docker_kwargs.get("volumes").get(source_dir)
    expected = "/opt/user_pip_packages,/opt/afni/build"
    assert docker_kwargs.get("environment")["CHOWN_EXTRA"] == expected
    assert docker_kwargs["environment"].get("CONTAINER_UID")

    # build should not be chowned if it is mounted
    source_dir, *_ = ce.get_path_strs_for_mounting(TESTS_DIR)
    docker_kwargs = ce.setup_docker_env_and_vol_settings(
        TESTS_DIR,
        **{"source_mode": "host", "build_dir": "a_directory"},
    )
    assert docker_kwargs.get("volumes").get(source_dir)
    expected = "/opt/user_pip_packages"
    assert docker_kwargs.get("environment")["CHOWN_EXTRA"] == expected
    assert docker_kwargs["environment"].get("CONTAINER_UID")

    # Confirm test-data volume is mounted
    _, data_dir, *_ = ce.get_path_strs_for_mounting(TESTS_DIR)
    docker_kwargs = ce.setup_docker_env_and_vol_settings(
        TESTS_DIR,
        **{"source_mode": "test-data-volume"},
    )
    expected = ['test_data']
    result = docker_kwargs.get("volumes_from")
    assert expected == result

    expected = "/opt"
    assert docker_kwargs.get("environment")["CHOWN_EXTRA"] == expected
    assert docker_kwargs["environment"].get("CONTAINER_UID")

    # Confirm tests directory is mounted and file permissions is set correctly
    _, data_dir, *_ = ce.get_path_strs_for_mounting(TESTS_DIR)
    docker_kwargs = ce.setup_docker_env_and_vol_settings(
        TESTS_DIR,
        **{"source_mode": "test-code"},
    )
    assert docker_kwargs.get("volumes").get(str(TESTS_DIR))
    expected = "/opt/afni/install,/opt/user_pip_packages"
    assert docker_kwargs.get("environment")["CHOWN_EXTRA"] == expected
    assert docker_kwargs["environment"].get("CONTAINER_UID")

    # Confirm build directory is mounted
    _, data_dir, *_ = ce.get_path_strs_for_mounting(TESTS_DIR)
    docker_kwargs = ce.setup_docker_env_and_vol_settings(
        TESTS_DIR,
        **{"build_dir": data_dir},
    )
    assert docker_kwargs.get("volumes").get(data_dir)
    assert not docker_kwargs["environment"].get("CONTAINER_UID")


def test_check_if_cmake_configure_required():
    # empty dir should work and require configure
    build_dir = Path(tempfile.mkdtemp())
    result = minfuncs.check_if_cmake_configure_required(build_dir)
    assert True == result

    # this should work. No actual pre-existing build but its assessed by a
    # cached file and the existence of build.ninja so fine for our purposes
    # here.
    ninja_dir = build_dir / "build.ninja"
    ninja_dir.mkdir()
    cache_file = build_dir / "CMakeCache.txt"
    cache_file.write_text(f"For build in directory: {build_dir}")
    result = minfuncs.check_if_cmake_configure_required(build_dir)
    assert False == result

    # this should work, weird path but is actually same directory
    unresolved_build_dir = build_dir.parent.joinpath(
        f"../{build_dir.parent.name}/{build_dir.name}"
    )
    result = minfuncs.check_if_cmake_configure_required(unresolved_build_dir)
    assert False == result

    # there is a cache but missing build.ninja so needs to be configured
    ninja_dir.rmdir()
    result = minfuncs.check_if_cmake_configure_required(build_dir)
    assert True == result

    # this should pass, missing dir but will be in container
    cache_file.write_text("For build in directory: /opt/afni/build")
    minfuncs.check_if_cmake_configure_required(build_dir, within_container=True)


def test_wrong_build_dir_raise_file_not_found(monkeypatch):
    build_dir = "/opt/afni/build"
    mocked_path_instance = Mock()
    mocked_path_instance.exists.return_value = False
    mocked_path = Mock()
    mocked_path.return_value = mocked_path_instance

    # mock non existent build dir
    monkeypatch.setattr(
        afni_test_utils.minimal_funcs_for_run_tests_cli, "Path", mocked_path
    )
    # mock local execution
    monkeypatch.setattr(
        afni_test_utils.minimal_funcs_for_run_tests_cli,
        "is_containerized",
        lambda x: False,
    )

    # this should fail, as /opt/build/afni is mocked to not exist, simulating
    # a local execution for which /opt/afni/build is specificed as the build
    # dir
    with pytest.raises(NotADirectoryError):
        afni_test_utils.minimal_funcs_for_run_tests_cli.check_if_cmake_configure_required(
            build_dir
        )
