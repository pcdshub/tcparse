#!../../bin/rhel7-x86_64/{{binary_name}}

< envPaths
epicsEnvSet("IOCNAME", "{{name}}" )
epicsEnvSet("ENGINEER", "{{user}}" )
epicsEnvSet("LOCATION", "{{prefix}}" )
epicsEnvSet("IOCSH_PS1", "$(IOCNAME)> " )

cd "$(TOP)"

# Run common startup commands for linux soft IOC's
< /reg/d/iocCommon/All/pre_linux.cmd

# Register all support components
dbLoadDatabase("dbd/{{binary_name}}.dbd")
{{binary_name}}_registerRecordDeviceDriver(pdbbase)

cd "$(TOP)/db"

epicsEnvSet("MOTOR_PORT",    "{{motor_port}}")
epicsEnvSet("ASYN_PORT",     "{{asyn_port}}")
epicsEnvSet("PREFIX",        "{{prefix}}")
epicsEnvSet("ECM_NUMAXES",   "{{motors|length}}")

epicsEnvSet("IPADDR",        "{{plc_ip}}")
epicsEnvSet("AMSID",         "{{plc_ams_id}}")
epicsEnvSet("IPPORT",        "{{plc_ads_port}}")
< "$(ETHERCATMC)/startup/EthercatMCController.cmd"

{% for motor in motors %}

epicsEnvSet("AXISCONFIG",    "{{motor.axisconfig}}")
epicsEnvSet("MOTOR_NAME",    "{{motor.name}}")
epicsEnvSet("AXIS_NO",       "{{motor.axis_no}}")
epicsEnvSet("DESC",          "{{motor.desc}}")
epicsEnvSet("EGU",           "{{motor.egu}}")
epicsEnvSet("PREC",          "{{motor.prec}}")
< "$(ETHERCATMC)/startup/EthercatMCAxis.cmd"
< "$(ETHERCATMC)/startup/EthercatMCAxisdebug.cmd"

{% endfor %}

cd "$(TOP)"

dbLoadRecords("db/iocAdmin.db", "P={{prefix}},IOC={{prefix}}" )
dbLoadRecords("db/save_restoreStatus.db", "P={{prefix}},IOC={{name}}" )

# Setup autosave
set_savefile_path( "$(IOC_DATA)/$(IOC)/autosave" )
set_requestfile_path( "$(TOP)/autosave" )
save_restoreSet_status_prefix( "{{prefix}}:" )
save_restoreSet_IncompleteSetsOk( 1 )
save_restoreSet_DatedBackupFiles( 1 )
set_pass0_restoreFile( "$(IOC).sav" )
set_pass1_restoreFile( "$(IOC).sav" )

# Initialize the IOC and start processing records
iocInit()

# Start autosave backups
create_monitor_set( "$(IOC).req", 5, "" )

# All IOCs should dump some common info after initial startup.
< /reg/d/iocCommon/All/post_linux.cmd
