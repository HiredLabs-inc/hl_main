import core_utils as core

# zoneStepper: given a zone and pay rate, returns a rate as a float 
def test_zoneAdjust_zoneC():
	assert core.zoneStepper(6,21.10,"General") == 10.71 

def test_zoneAdjust_zoneD():
	assert core.zoneStepper(5,21.10,"General") == 12.00 

def test_zoneAdjust_zoneE():
	assert core.zoneStepper(4,21.10,"General") == 13.40 

def test_zoneAdjust_zoneF():
	assert core.zoneStepper(3,21.10,"General") == 15.00 

def test_zoneAdjust_zoneG():
	assert core.zoneStepper(2,21.10,"General") == 16.80 

def test_zoneAdjust_zoneH():
	assert core.zoneStepper(1,21.10,"General") == 18.80 

def test_zoneAdjust_zoneI():
	assert core.zoneStepper(0,21.10,"General") == 21.10 

# levelStepper: given a level, zone, and rate, returns a rate as a float
# ZONE C (6)
def test_levelAdjust_zoneC_L1():
	assert core.levelStepper(1,6,10.71,"General") == 10.71 

def test_levelAdjust_zoneC_L2():
	assert core.levelStepper(2,6,10.71,"General") == 11.80

def test_levelAdjust_zoneC_L3():
	assert core.levelStepper(3,6,10.71,"General") == 13.00

def test_levelAdjust_zoneC_L4():
	assert core.levelStepper(4,6,10.71,"General") == 14.30

def test_levelAdjust_zoneC_L5():
	assert core.levelStepper(5,6,10.71,"General") == 15.70

def test_levelAdjust_zoneC_L6():
	assert core.levelStepper(6,6,10.71,"General") == 18.80

def test_levelAdjust_zoneC_L7():
	assert core.levelStepper(7,6,10.71,"General") == 20.70

def test_levelAdjust_zoneC_L8():
	assert core.levelStepper(8,6,10.71,"General") == 22.80

def test_levelAdjust_zoneC_L9():
	assert core.levelStepper(9,6,10.71,"General") == 27.40

def test_levelAdjust_zoneC_L10():
	assert core.levelStepper(10,6,10.71,"General") == 30.10

def test_levelAdjust_zoneC_L11():
	assert core.levelStepper(11,6,10.71,"General") == 33.10

# ZONE D (5)
def test_levelAdjust_zoneD_L1():
	assert core.levelStepper(1,5,12.00,"General") == 12.00

def test_levelAdjust_zoneD_L2():
	assert core.levelStepper(2,5,12.00,"General") == 13.20

def test_levelAdjust_zoneD_L3():
	assert core.levelStepper(3,5,12.00,"General") == 14.50

def test_levelAdjust_zoneD_L4():
	assert core.levelStepper(4,5,12.00,"General") == 16.00

def test_levelAdjust_zoneD_L5():
	assert core.levelStepper(5,5,12.00,"General") == 17.60

def test_levelAdjust_zoneD_L6():
	assert core.levelStepper(6,5,12.00,"General") == 21.10

def test_levelAdjust_zoneD_L7():
	assert core.levelStepper(7,5,12.00,"General") == 23.20

def test_levelAdjust_zoneD_L8():
	assert core.levelStepper(8,5,12.00,"General") == 25.50

def test_levelAdjust_zoneD_L9():
	assert core.levelStepper(9,5,12.00,"General") == 30.60

def test_levelAdjust_zoneD_L10():
	assert core.levelStepper(10,5,12.00,"General") == 33.70

def test_levelAdjust_zoneD_L11():
	assert core.levelStepper(11,5,12.00,"General") == 37.10

# ZONE E (4)
def test_levelAdjust_zoneE_L1():
	assert core.levelStepper(1,4,13.40,"General") == 13.40

def test_levelAdjust_zoneE_L2():
	assert core.levelStepper(2,4,13.40,"General") == 14.70

def test_levelAdjust_zoneE_L3():
	assert core.levelStepper(3,4,13.40,"General") == 16.20

def test_levelAdjust_zoneE_L4():
	assert core.levelStepper(4,4,13.40,"General") == 17.80

def test_levelAdjust_zoneE_L5():
	assert core.levelStepper(5,4,13.40,"General") == 19.60

def test_levelAdjust_zoneE_L6():
	assert core.levelStepper(6,4,13.40,"General") == 23.50

def test_levelAdjust_zoneE_L7():
	assert core.levelStepper(7,4,13.40,"General") == 25.90

def test_levelAdjust_zoneE_L8():
	assert core.levelStepper(8,4,13.40,"General") == 28.50

def test_levelAdjust_zoneE_L9():
	assert core.levelStepper(9,4,13.40,"General") == 34.20

def test_levelAdjust_zoneE_L10():
	assert core.levelStepper(10,4,13.40,"General") == 37.60

def test_levelAdjust_zoneE_L11():
	assert core.levelStepper(11,4,13.40,"General") == 41.40

# ZONE F (3)
def test_levelAdjust_zoneF_L1():
	assert core.levelStepper(1,3,15.00,"General") == 15.00

def test_levelAdjust_zoneF_L2():
	assert core.levelStepper(2,3,15.00,"General") == 16.50

def test_levelAdjust_zoneF_L3():
	assert core.levelStepper(3,3,15.00,"General") == 18.20

def test_levelAdjust_zoneF_L4():
	assert core.levelStepper(4,3,15.00,"General") == 20.00

def test_levelAdjust_zoneF_L5():
	assert core.levelStepper(5,3,15.00,"General") == 22.00

def test_levelAdjust_zoneF_L6():
	assert core.levelStepper(6,3,15.00,"General") == 26.40

def test_levelAdjust_zoneF_L7():
	assert core.levelStepper(7,3,15.00,"General") == 29.00

def test_levelAdjust_zoneF_L8():
	assert core.levelStepper(8,3,15.00,"General") == 31.90

def test_levelAdjust_zoneF_L9():
	assert core.levelStepper(9,3,15.00,"General") == 38.30

def test_levelAdjust_zoneF_L10():
	assert core.levelStepper(10,3,15.00,"General") == 42.10

def test_levelAdjust_zoneF_L11():
	assert core.levelStepper(11,3,15.00,"General") == 46.30

# ZONE G (2)
def test_levelAdjust_zoneG_L1():
	assert core.levelStepper(1,2,16.80,"General") == 16.80

def test_levelAdjust_zoneG_L2():
	assert core.levelStepper(2,2,16.80,"General") == 18.50

def test_levelAdjust_zoneG_L3():
	assert core.levelStepper(3,2,16.80,"General") == 20.40

def test_levelAdjust_zoneG_L4():
	assert core.levelStepper(4,2,16.80,"General") == 22.40

def test_levelAdjust_zoneG_L5():
	assert core.levelStepper(5,2,16.80,"General") == 24.60

def test_levelAdjust_zoneG_L6():
	assert core.levelStepper(6,2,16.80,"General") == 29.50

def test_levelAdjust_zoneG_L7():
	assert core.levelStepper(7,2,16.80,"General") == 32.50

def test_levelAdjust_zoneG_L8():
	assert core.levelStepper(8,2,16.80,"General") == 35.80

def test_levelAdjust_zoneG_L9():
	assert core.levelStepper(9,2,16.80,"General") == 43.00

def test_levelAdjust_zoneG_L10():
	assert core.levelStepper(10,2,16.80,"General") == 47.30

def test_levelAdjust_zoneG_L11():
	assert core.levelStepper(11,2,16.80,"General") == 52.00

# ZONE H (1)
def test_levelAdjust_zoneH_L1():
	assert core.levelStepper(1,1,18.80,"General") == 18.80

def test_levelAdjust_zoneH_L2():
	assert core.levelStepper(2,1,18.80,"General") == 20.70

def test_levelAdjust_zoneH_L3():
	assert core.levelStepper(3,1,18.80,"General") == 22.80

def test_levelAdjust_zoneH_L4():
	assert core.levelStepper(4,1,18.80,"General") == 25.10

def test_levelAdjust_zoneH_L5():
	assert core.levelStepper(5,1,18.80,"General") == 27.60

def test_levelAdjust_zoneH_L6():
	assert core.levelStepper(6,1,18.80,"General") == 33.10

def test_levelAdjust_zoneH_L7():
	assert core.levelStepper(7,1,18.80,"General") == 36.40

def test_levelAdjust_zoneH_L8():
	assert core.levelStepper(8,1,18.80,"General") == 40.00

def test_levelAdjust_zoneH_L9():
	assert core.levelStepper(9,1,18.80,"General") == 48.00

def test_levelAdjust_zoneH_L10():
	assert core.levelStepper(10,1,18.80,"General") == 52.80

def test_levelAdjust_zoneH_L11():
	assert core.levelStepper(11,1,18.80,"General") == 58.10

# ZONE I (0)
def test_levelAdjust_zoneI_L1():
	assert core.levelStepper(1,0,21.10,"General") == 21.10

def test_levelAdjust_zoneI_L2():
	assert core.levelStepper(2,0,21.10,"General") == 23.20

def test_levelAdjust_zoneI_L3():
	assert core.levelStepper(3,0,21.10,"General") == 25.50

def test_levelAdjust_zoneI_L4():
	assert core.levelStepper(4,0,21.10,"General") == 28.10

def test_levelAdjust_zoneI_L5():
	assert core.levelStepper(5,0,21.10,"General") == 30.90

def test_levelAdjust_zoneI_L6():
	assert core.levelStepper(6,0,21.10,"General") == 37.10

def test_levelAdjust_zoneI_L7():
	assert core.levelStepper(7,0,21.10,"General") == 40.80

def test_levelAdjust_zoneI_L8():
	assert core.levelStepper(8,0,21.10,"General") == 44.90

def test_levelAdjust_zoneI_L9():
	assert core.levelStepper(9,0,21.10,"General") == 53.90

def test_levelAdjust_zoneI_L10():
	assert core.levelStepper(10,0,21.10,"General") == 59.30

def test_levelAdjust_zoneI_L11():
	assert core.levelStepper(11,0,21.10,"General") == 65.20

# bigStepper: given a level, zone and reference rate, returns pay rate as float
def test_bigStepper_zoneC_L1():
	assert core.bigStepper(1,6,21.10,"General") == 10.71

def test_bigStepper_zoneC_L4():
	assert core.bigStepper(4,6,21.10,"General") == 14.30

def test_bigStepper_zoneC_L8():
	assert core.bigStepper(8,6,21.10,"General") == 22.80

def test_bigStepper_zoneD_L3():
	assert core.bigStepper(3,5,21.10,"General") == 14.50

def test_bigStepper_zoneD_L7():
	assert core.bigStepper(7,5,21.10,"General") ==  23.20

def test_bigStepper_zoneE_L2():
	assert core.bigStepper(2,4,21.10,"General") == 14.70

def test_bigStepper_zoneE_L11():
	assert core.bigStepper(11,4,21.10,"General") ==  41.40

def test_bigStepper_zoneF_L5():
	assert core.bigStepper(5,3,21.10,"General") == 22.00

def test_bigStepper_zoneF_L9():
	assert core.bigStepper(9,3,21.10,"General") == 38.30

def test_bigStepper_zoneG_L3():
	assert core.bigStepper(3,2,21.10,"General") == 20.40

def test_bigStepper_zoneG_L10():
	assert core.bigStepper(10,2,21.10,"General") == 47.30

def test_bigStepper_zoneH_L2():
	assert core.bigStepper(2,1,21.10,"General") == 20.70

def test_bigStepper_zoneH_L11():
	assert core.bigStepper(11,1,21.10,"General") == 58.10

def test_bigStepper_zoneI_L4():
	assert core.bigStepper(4,0,21.10,"General") == 28.10

def test_bigStepper_zoneI_L7():
	assert core.bigStepper(7,0,21.10,"General") == 40.80

#Full-stack tests
# bigStepper: given a level, zone and reference rate, returns pay rate as float
def test_fs_bigStepper_zoneC_L1():
	assert core.bigStepper(1,6,35.30,"Full-stack Engineering") == 17.85

def test_fs_bigStepper_zoneC_L4():
	assert core.bigStepper(4,6,35.30,"Full-stack Engineering") == 23.80

def test_fs_bigStepper_zoneC_L8():
	assert core.bigStepper(8,6,35.30,"Full-stack Engineering") == 38.00

def test_fs_bigStepper_zoneD_L3():
	assert core.bigStepper(3,5,35.30,"Full-stack Engineering") == 24.20

def test_fs_bigStepper_zoneD_L7():
	assert core.bigStepper(7,5,35.30,"Full-stack Engineering") ==  38.70

def test_fs_bigStepper_zoneE_L2():
	assert core.bigStepper(2,4,35.30,"Full-stack Engineering") == 24.60

def test_fs_bigStepper_zoneE_L11():
	assert core.bigStepper(11,4,35.30,"Full-stack Engineering") ==  69.10

def test_fs_bigStepper_zoneF_L5():
	assert core.bigStepper(5,3,35.30,"Full-stack Engineering") == 36.70

def test_fs_bigStepper_zoneF_L9():
	assert core.bigStepper(9,3,35.30,"Full-stack Engineering") == 63.80

def test_fs_bigStepper_zoneG_L3():
	assert core.bigStepper(3,2,35.30,"Full-stack Engineering") == 34.00

def test_fs_bigStepper_zoneG_L10():
	assert core.bigStepper(10,2,35.30,"Full-stack Engineering") == 78.70

def test_fs_bigStepper_zoneH_L2():
	assert core.bigStepper(2,1,35.30,"Full-stack Engineering") == 34.70

def test_fs_bigStepper_zoneH_L11():
	assert core.bigStepper(11,1,35.30,"Full-stack Engineering") == 97.20

def test_fs_bigStepper_zoneI_L4():
	assert core.bigStepper(4,0,35.30,"Full-stack Engineering") == 47.00

def test_fs_bigStepper_zoneI_L7():
	assert core.bigStepper(7,0,35.30,"Full-stack Engineering") == 68.20

#Product Architecture tests
# bigStepper: given a level, zone and reference rate, returns pay rate as float
def test_pa_bigStepper_zoneC_L1():
	assert core.bigStepper(1,6,35.30,"Product Architecture") == 17.85

def test_pa_bigStepper_zoneC_L4():
	assert core.bigStepper(4,6,35.30,"Product Architecture") == 23.80

def test_pa_bigStepper_zoneC_L8():
	assert core.bigStepper(8,6,35.30,"Product Architecture") == 38.00

def test_pa_bigStepper_zoneD_L3():
	assert core.bigStepper(3,5,35.30,"Product Architecture") == 24.20

def test_pa_bigStepper_zoneD_L7():
	assert core.bigStepper(7,5,35.30,"Product Architecture") ==  38.70

def test_pa_bigStepper_zoneE_L2():
	assert core.bigStepper(2,4,35.30,"Product Architecture") == 24.60

def test_pa_bigStepper_zoneE_L11():
	assert core.bigStepper(11,4,35.30,"Product Architecture") ==  69.10

def test_pa_bigStepper_zoneF_L5():
	assert core.bigStepper(5,3,35.30,"Product Architecture") == 36.70

def test_pa_bigStepper_zoneF_L9():
	assert core.bigStepper(9,3,35.30,"Product Architecture") == 63.80

def test_pa_bigStepper_zoneG_L3():
	assert core.bigStepper(3,2,35.30,"Product Architecture") == 34.00

def test_pa_bigStepper_zoneG_L10():
	assert core.bigStepper(10,2,35.30,"Product Architecture") == 78.70

def test_pa_bigStepper_zoneH_L2():
	assert core.bigStepper(2,1,35.30,"Product Architecture") == 34.70

def test_pa_bigStepper_zoneH_L11():
	assert core.bigStepper(11,1,35.30,"Product Architecture") == 97.20

def test_pa_bigStepper_zoneI_L4():
	assert core.bigStepper(4,0,35.30,"Product Architecture") == 47.00

def test_pa_bigStepper_zoneI_L7():
	assert core.bigStepper(7,0,35.30,"Product Architecture") == 68.20

#Product Management tests
# bigStepper: given a level, zone and reference rate, returns pay rate as float
def test_pm_bigStepper_zoneC_L1():
	assert core.bigStepper(1,6,35.30,"Product Management") == 17.85

def test_pm_bigStepper_zoneC_L4():
	assert core.bigStepper(4,6,35.30,"Product Management") == 23.80

def test_pm_bigStepper_zoneC_L8():
	assert core.bigStepper(8,6,35.30,"Product Management") == 38.00

def test_pm_bigStepper_zoneD_L3():
	assert core.bigStepper(3,5,35.30,"Product Management") == 24.20

def test_pm_bigStepper_zoneD_L7():
	assert core.bigStepper(7,5,35.30,"Product Management") ==  38.70

def test_pm_bigStepper_zoneE_L2():
	assert core.bigStepper(2,4,35.30,"Product Management") == 24.60

def test_pm_bigStepper_zoneE_L11():
	assert core.bigStepper(11,4,35.30,"Product Management") ==  69.10

def test_pm_bigStepper_zoneF_L5():
	assert core.bigStepper(5,3,35.30,"Product Management") == 36.70

def test_pm_bigStepper_zoneF_L9():
	assert core.bigStepper(9,3,35.30,"Product Management") == 63.80

def test_pm_bigStepper_zoneG_L3():
	assert core.bigStepper(3,2,35.30,"Product Management") == 34.00

def test_pm_bigStepper_zoneG_L10():
	assert core.bigStepper(10,2,35.30,"Product Management") == 78.70

def test_pm_bigStepper_zoneH_L2():
	assert core.bigStepper(2,1,35.30,"Product Management") == 34.70

def test_pm_bigStepper_zoneH_L11():
	assert core.bigStepper(11,1,35.30,"Product Management") == 97.20

def test_pm_bigStepper_zoneI_L4():
	assert core.bigStepper(4,0,35.30,"Product Management") == 47.00

def test_pm_bigStepper_zoneI_L7():
	assert core.bigStepper(7,0,35.30,"Product Management") == 68.20

#Automated QA tests
# bigStepper: given a level, zone and reference rate, returns pay rate as float
def test_auto_qa_bigStepper_zoneC_L1():
	assert core.bigStepper(1,6,24.90,"Automated QA") == 12.64

def test_auto_qa_bigStepper_zoneC_L4():
	assert core.bigStepper(4,6,24.90,"Automated QA") == 16.87

def test_auto_qa_bigStepper_zoneC_L8():
	assert core.bigStepper(8,6,24.90,"Automated QA") == 26.90

def test_auto_qa_bigStepper_zoneD_L3():
	assert core.bigStepper(3,5,24.90,"Automated QA") == 17.11

def test_auto_qa_bigStepper_zoneD_L7():
	assert core.bigStepper(7,5,24.90,"Automated QA") ==  27.38

def test_auto_qa_bigStepper_zoneE_L2():
	assert core.bigStepper(2,4,24.90,"Automated QA") == 17.35

def test_auto_qa_bigStepper_zoneE_L11():
	assert core.bigStepper(11,4,24.90,"Automated QA") ==  48.85

def test_auto_qa_bigStepper_zoneF_L5():
	assert core.bigStepper(5,3,24.90,"Automated QA") == 25.96

def test_auto_qa_bigStepper_zoneF_L9():
	assert core.bigStepper(9,3,24.90,"Automated QA") == 45.19

def test_auto_qa_bigStepper_zoneG_L3():
	assert core.bigStepper(3,2,24.90,"Automated QA") == 24.07

def test_auto_qa_bigStepper_zoneG_L10():
	assert core.bigStepper(10,2,24.90,"Automated QA") == 55.81

def test_auto_qa_bigStepper_zoneH_L2():
	assert core.bigStepper(2,1,24.90,"Automated QA") == 24.43

def test_auto_qa_bigStepper_zoneH_L11():
	assert core.bigStepper(11,1,24.90,"Automated QA") == 68.56

def test_auto_qa_bigStepper_zoneI_L4():
	assert core.bigStepper(4,0,24.90,"Automated QA") == 33.16

def test_auto_qa_bigStepper_zoneI_L7():
	assert core.bigStepper(7,0,24.90,"Automated QA") == 48.14

#Mobile Development tests
# bigStepper: given a level, zone and reference rate, returns pay rate as float
def test_md_bigStepper_zoneC_L1():
	assert core.bigStepper(1,6,40.10,"Mobile Development") == 20.40

def test_md_bigStepper_zoneC_L4():
	assert core.bigStepper(4,6,40.10,"Mobile Development") == 27.10

def test_md_bigStepper_zoneC_L8():
	assert core.bigStepper(8,6,40.10,"Mobile Development") == 43.30

def test_md_bigStepper_zoneD_L3():
	assert core.bigStepper(3,5,40.10,"Mobile Development") == 27.60

def test_md_bigStepper_zoneD_L7():
	assert core.bigStepper(7,5,40.10,"Mobile Development") ==  44.10

def test_md_bigStepper_zoneE_L2():
	assert core.bigStepper(2,4,40.10,"Mobile Development") == 28.10

def test_md_bigStepper_zoneE_L11():
	assert core.bigStepper(11,4,40.10,"Mobile Development") ==  78.90

def test_md_bigStepper_zoneF_L5():
	assert core.bigStepper(5,3,40.10,"Mobile Development") == 42.00

def test_md_bigStepper_zoneF_L9():
	assert core.bigStepper(9,3,40.10,"Mobile Development") == 73.10

def test_md_bigStepper_zoneG_L3():
	assert core.bigStepper(3,2,40.10,"Mobile Development") == 38.70

def test_md_bigStepper_zoneG_L10():
	assert core.bigStepper(10,2,40.10,"Mobile Development") == 89.90

def test_md_bigStepper_zoneH_L2():
	assert core.bigStepper(2,1,40.10,"Mobile Development") == 39.40

def test_md_bigStepper_zoneH_L11():
	assert core.bigStepper(11,1,40.10,"Mobile Development") == 110.40

def test_md_bigStepper_zoneI_L4():
	assert core.bigStepper(4,0,40.10,"Mobile Development") == 53.40

def test_md_bigStepper_zoneI_L7():
	assert core.bigStepper(7,0,40.10,"Mobile Development") == 77.40

#Technical Writer tests
# bigStepper: given a level, zone and reference rate, returns pay rate as float
def test_tw_bigStepper_zoneC_L1():
	assert core.bigStepper(1,6,19.20,"Technical Writer") == 9.69

def test_tw_bigStepper_zoneC_L4():
	assert core.bigStepper(4,6,19.20,"Technical Writer") == 13.00

def test_tw_bigStepper_zoneC_L8():
	assert core.bigStepper(8,6,19.20,"Technical Writer") == 20.80

def test_tw_bigStepper_zoneD_L3():
	assert core.bigStepper(3,5,19.20,"Technical Writer") == 13.20

def test_tw_bigStepper_zoneD_L7():
	assert core.bigStepper(7,5,19.20,"Technical Writer") ==  21.10

def test_tw_bigStepper_zoneE_L2():
	assert core.bigStepper(2,4,19.20,"Technical Writer") == 13.40

def test_tw_bigStepper_zoneE_L11():
	assert core.bigStepper(11,4,19.20,"Technical Writer") ==  37.60

def test_tw_bigStepper_zoneF_L5():
	assert core.bigStepper(5,3,19.20,"Technical Writer") == 20.10

def test_tw_bigStepper_zoneF_L9():
	assert core.bigStepper(9,3,19.20,"Technical Writer") == 35.00

def test_tw_bigStepper_zoneG_L3():
	assert core.bigStepper(3,2,19.20,"Technical Writer") == 18.50

def test_tw_bigStepper_zoneG_L10():
	assert core.bigStepper(10,2,19.20,"Technical Writer") == 43.00

def test_tw_bigStepper_zoneH_L2():
	assert core.bigStepper(2,1,19.20,"Technical Writer") == 18.80

def test_tw_bigStepper_zoneH_L11():
	assert core.bigStepper(11,1,19.20,"Technical Writer") == 52.90

def test_tw_bigStepper_zoneI_L4():
	assert core.bigStepper(4,0,19.20,"Technical Writer") == 25.50

def test_tw_bigStepper_zoneI_L7():
	assert core.bigStepper(7,0,19.20,"Technical Writer") == 37.10

#Recruiting tests
# bigStepper: given a level, zone and reference rate, returns pay rate as float
def test_rec_bigStepper_zoneC_L1():
	assert core.bigStepper(1,6,26.20,"Recruiting") == 13.26

def test_rec_bigStepper_zoneC_L4():
	assert core.bigStepper(4,6,26.20,"Recruiting") == 17.70

def test_rec_bigStepper_zoneC_L8():
	assert core.bigStepper(8,6,26.20,"Recruiting") == 28.30

def test_rec_bigStepper_zoneD_L3():
	assert core.bigStepper(3,5,26.20,"Recruiting") == 18.00

def test_rec_bigStepper_zoneD_L7():
	assert core.bigStepper(7,5,26.20,"Recruiting") ==  28.80

def test_rec_bigStepper_zoneE_L2():
	assert core.bigStepper(2,4,26.20,"Recruiting") == 18.40

def test_rec_bigStepper_zoneE_L11():
	assert core.bigStepper(11,4,26.20,"Recruiting") ==  51.50

def test_rec_bigStepper_zoneF_L5():
	assert core.bigStepper(5,3,26.20,"Recruiting") == 27.50

def test_rec_bigStepper_zoneF_L9():
	assert core.bigStepper(9,3,26.20,"Recruiting") == 47.90

def test_rec_bigStepper_zoneG_L3():
	assert core.bigStepper(3,2,26.20,"Recruiting") == 25.30

def test_rec_bigStepper_zoneG_L10():
	assert core.bigStepper(10,2,26.20,"Recruiting") == 58.60

def test_rec_bigStepper_zoneH_L2():
	assert core.bigStepper(2,1,26.20,"Recruiting") == 25.70

def test_rec_bigStepper_zoneH_L11():
	assert core.bigStepper(11,1,26.20,"Recruiting") == 72.10

def test_rec_bigStepper_zoneI_L4():
	assert core.bigStepper(4,0,26.20,"Recruiting") == 34.90

def test_rec_bigStepper_zoneI_L7():
	assert core.bigStepper(7,0,26.20,"Recruiting") == 50.70

#Data Science tests
# bigStepper: given a level, zone and reference rate, returns pay rate as float
def test_ds_bigStepper_zoneC_L1():
	assert core.bigStepper(1,6,28.10,"Data Science") == 14.28

def test_ds_bigStepper_zoneC_L4():
	assert core.bigStepper(4,6,28.10,"Data Science") == 19.00

def test_ds_bigStepper_zoneC_L8():
	assert core.bigStepper(8,6,28.10,"Data Science") == 30.40

def test_ds_bigStepper_zoneD_L3():
	assert core.bigStepper(3,5,28.10,"Data Science") == 19.40

def test_ds_bigStepper_zoneD_L7():
	assert core.bigStepper(7,5,28.10,"Data Science") ==  30.90

def test_ds_bigStepper_zoneE_L2():
	assert core.bigStepper(2,4,28.10,"Data Science") == 19.70

def test_ds_bigStepper_zoneE_L11():
	assert core.bigStepper(11,4,28.10,"Data Science") ==  55.70

def test_ds_bigStepper_zoneF_L5():
	assert core.bigStepper(5,3,28.10,"Data Science") == 29.30

def test_ds_bigStepper_zoneF_L9():
	assert core.bigStepper(9,3,28.10,"Data Science") == 51.10

def test_ds_bigStepper_zoneG_L3():
	assert core.bigStepper(3,2,28.10,"Data Science") == 27.10

def test_ds_bigStepper_zoneG_L10():
	assert core.bigStepper(10,2,28.10,"Data Science") == 62.80

def test_ds_bigStepper_zoneH_L2():
	assert core.bigStepper(2,1,28.10,"Data Science") == 27.60

def test_ds_bigStepper_zoneH_L11():
	assert core.bigStepper(11,1,28.10,"Data Science") == 77.20

def test_ds_bigStepper_zoneI_L4():
	assert core.bigStepper(4,0,28.10,"Data Science") == 37.40

def test_ds_bigStepper_zoneI_L7():
	assert core.bigStepper(7,0,28.10,"Data Science") == 54.20

#Tech Ops tests
# bigStepper: given a level, zone and reference rate, returns pay rate as float
def test_to_bigStepper_zoneC_L1():
	assert core.bigStepper(1,6,28.10,"Tech Ops") == 14.28

def test_to_bigStepper_zoneC_L4():
	assert core.bigStepper(4,6,28.10,"Tech Ops") == 19.00

def test_to_bigStepper_zoneC_L8():
	assert core.bigStepper(8,6,28.10,"Tech Ops") == 30.40

def test_to_bigStepper_zoneD_L3():
	assert core.bigStepper(3,5,28.10,"Tech Ops") == 19.40

def test_to_bigStepper_zoneD_L7():
	assert core.bigStepper(7,5,28.10,"Tech Ops") ==  30.90

def test_to_bigStepper_zoneE_L2():
	assert core.bigStepper(2,4,28.10,"Tech Ops") == 19.70

def test_to_bigStepper_zoneE_L11():
	assert core.bigStepper(11,4,28.10,"Tech Ops") ==  55.70

def test_to_bigStepper_zoneF_L5():
	assert core.bigStepper(5,3,28.10,"Tech Ops") == 29.30

def test_to_bigStepper_zoneF_L9():
	assert core.bigStepper(9,3,28.10,"Tech Ops") == 51.10

def test_to_bigStepper_zoneG_L3():
	assert core.bigStepper(3,2,28.10,"Tech Ops") == 27.10

def test_to_bigStepper_zoneG_L10():
	assert core.bigStepper(10,2,28.10,"Tech Ops") == 62.80

def test_to_bigStepper_zoneH_L2():
	assert core.bigStepper(2,1,28.10,"Tech Ops") == 27.60

def test_to_bigStepper_zoneH_L11():
	assert core.bigStepper(11,1,28.10,"Tech Ops") == 77.20

def test_to_bigStepper_zoneI_L4():
	assert core.bigStepper(4,0,28.10,"Tech Ops") == 37.40

def test_to_bigStepper_zoneI_L7():
	assert core.bigStepper(7,0,28.10,"Tech Ops") == 54.20

#Tech Support tests
# bigStepper: given a level, zone and reference rate, returns pay rate as float
def test_ts_bigStepper_zoneC_L1():
	assert core.bigStepper(1,6,20.00,"Tech Support") == 10.20

def test_ts_bigStepper_zoneC_L4():
	assert core.bigStepper(4,6,20.00,"Tech Support") == 13.50

def test_ts_bigStepper_zoneC_L8():
	assert core.bigStepper(8,6,20.00,"Tech Support") == 21.70

def test_ts_bigStepper_zoneD_L3():
	assert core.bigStepper(3,5,20.00,"Tech Support") == 13.80

def test_ts_bigStepper_zoneD_L7():
	assert core.bigStepper(7,5,20.00,"Tech Support") == 22.00

def test_ts_bigStepper_zoneE_L2():
	assert core.bigStepper(2,4,20.00,"Tech Support") == 14.10

def test_ts_bigStepper_zoneE_L11():
	assert core.bigStepper(11,4,20.00,"Tech Support") == 39.80

def test_ts_bigStepper_zoneF_L5():
	assert core.bigStepper(5,3,20.00,"Tech Support") == 20.90

def test_ts_bigStepper_zoneF_L9():
	assert core.bigStepper(9,3,20.00,"Tech Support") == 36.50

def test_ts_bigStepper_zoneG_L3():
	assert core.bigStepper(3,2,20.00,"Tech Support") == 19.40

def test_ts_bigStepper_zoneG_L10():
	assert core.bigStepper(10,2,20.00,"Tech Support") == 44.90

def test_ts_bigStepper_zoneH_L2():
	assert core.bigStepper(2,1,20.00,"Tech Support") == 19.70

def test_ts_bigStepper_zoneH_L11():
	assert core.bigStepper(11,1,20.00,"Tech Support") == 55.70

def test_ts_bigStepper_zoneI_L4():
	assert core.bigStepper(4,0,20.00,"Tech Support") == 26.60

def test_ts_bigStepper_zoneI_L7():
	assert core.bigStepper(7,0,20.00,"Tech Support") == 38.70
