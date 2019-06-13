from .conftest import TEST_ROOT

from ..parse import get_pou_call_blocks, parse


def test_call_blocks():
    decl = '''
        PROGRAM Main
        VAR
                M1: FB_DriveVirtual;
                M1Link: FB_NcAxis;
                bLimitFwdM1 AT %I*: BOOL;
                bLimitBwdM1 AT %I*: BOOL;

        END_VAR
    '''

    impl = '''
        M1Link(En := TRUE);
        M1(En := TRUE,
           bEnable := TRUE,
           bLimitFwd := bLimitFwdM1,
           bLimitBwd := bLimitBwdM1,
           Axis := M1Link.axis);

        M1(En := FALSE);
    '''

    assert get_pou_call_blocks(decl, impl) == {
        'M1': {'En': 'FALSE',
               'bEnable': 'TRUE',
               'bLimitFwd': 'bLimitFwdM1',
               'bLimitBwd': 'bLimitBwdM1',
               'Axis': 'M1Link.axis'},
        'M1Link': {'En': 'TRUE'}
    }


def test_route_parsing():
    # located in: C:\twincat\3.1\StaticRoutes.xml
    routes = parse(TEST_ROOT / 'static_routes.xml')
    remote_connections = routes.RemoteConnections[0]
    assert remote_connections.by_name == {
        'LAMP-VACUUM': {
            'Name': 'LAMP-VACUUM',
            'Address': '172.21.37.140',
            'NetId': '5.21.50.18.1.1',
            'Type': 'TCP_IP'
        },
        'AMO-BASE': {
            'Name': 'AMO-BASE',
            'Address': '172.21.37.114',
            'NetId': '5.17.65.196.1.1',
            'Type': 'TCP_IP'
        },
    }

    assert remote_connections.by_address == {
        '172.21.37.114': {'Address': '172.21.37.114',
                          'Name': 'AMO-BASE',
                          'NetId': '5.17.65.196.1.1',
                          'Type': 'TCP_IP'},
        '172.21.37.140': {'Address': '172.21.37.140',
                          'Name': 'LAMP-VACUUM',
                          'NetId': '5.21.50.18.1.1',
                          'Type': 'TCP_IP'}
        }

    assert remote_connections.by_ams_id == {
        '5.17.65.196.1.1': {
            'Address': '172.21.37.114',
            'Name': 'AMO-BASE',
            'NetId': '5.17.65.196.1.1',
            'Type': 'TCP_IP'
        },
        '5.21.50.18.1.1': {
            'Address': '172.21.37.140',
            'Name': 'LAMP-VACUUM',
            'NetId': '5.21.50.18.1.1',
            'Type': 'TCP_IP'
        },
    }

