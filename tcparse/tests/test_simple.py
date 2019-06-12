from ..parse import get_pou_call_blocks


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
