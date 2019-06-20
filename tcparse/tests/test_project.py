import tcparse
import pprint


def test_load_and_repr(project):
    info = repr(project)
    print(info[:1000], '...')


def test_summarize(project):
    assert project.root is project
    for cls in [tcparse.Axis, tcparse.Encoder]:
        for inst in project.find(cls):
            print(inst.qualified_path)
            print('-----------------')
            pprint.pprint(dict(inst.summarize()))

    for inst in project.find(tcparse.Symbol):
        pprint.pprint(inst.info)
        inst.project


def test_module_ads_port(project):
    for inst in project.find(tcparse.Module):
        assert inst.ads_port == 851  # probably!


def test_smoke_ams_id(project):
    print(project.ams_id)
    print(project.target_ip)


def test_fb_motionstage_linking(project):
    for inst in project.find(tcparse.Symbol_FB_MotionStage):
        pprint.pprint(inst)
        print('Program name', inst.program_name)
        print('Motor name', inst.motor_name)
        print('POU', inst.pou)
        inst.pou.variables  # smoke testing
        print('Call block', inst.call_block)
        print('Linked to', inst.linked_to)
        print('NC to PLC link', inst.nc_to_plc_link)

        nc_axis = inst.nc_axis
        print('Short NC axis name', nc_axis.short_name)
        print('NC axis', nc_axis)
