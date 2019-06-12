import pytest
import pathlib

from .. import load_project


TEST_ROOT = pathlib.Path(__file__).parent


@pytest.fixture(params=list(str(fn) for fn in TEST_ROOT.glob('**/*.tsproj')))
def project_filename(request):
    return request.param


@pytest.fixture(scope='function')
def project(project_filename):
    return load_project(project_filename)
