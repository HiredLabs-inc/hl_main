from rates.static.scripts.rate_core import steps


def zoneStepper(zone, ref_rate, title):
    if title == 'Full-stack Engineering' or title == 'Product Architecture' or title == 'Product Management':
        return round(ref_rate * steps.fs_pa_pm_zone_steps[zone], 2)
    elif title == 'Automated QA':
        return round(ref_rate * steps.automated_qa_zone_steps[zone], 2)
    elif title == 'Mobile Development':
        return round(ref_rate * steps.mobile_zone_steps[zone], 2)
    elif title == 'Technical Writer':
        return round(ref_rate * steps.tech_writer_zone_steps[zone], 2)
    elif title == 'Recruiting':
        return round(ref_rate * steps.recruiting_zone_steps[zone], 2)
    elif title == 'Data Science' or title == 'Tech Ops':
        return round(ref_rate * steps.data_science_tech_ops_zone_steps[zone], 2)
    elif title == 'Tech Support':
        return round(ref_rate * steps.tech_support_zone_steps[zone], 2)
    else:
        return round(ref_rate * steps.zone_steps[zone], 2)


def levelStepper(level, zone, rate, title):
    if title == 'Full-stack Engineering' or title == 'Product Architecture' or title == 'Product Management':
        return round(rate * steps.fs_pa_pm_level_steps[zone][level - 1], 2)
    elif title == 'Automated QA':
        return round(rate * steps.automated_qa_level_steps[zone][level - 1], 2)
    elif title == 'Mobile Development':
        return round(rate * steps.mobile_level_steps[zone][level - 1], 2)
    elif title == 'Technical Writer':
        return round(rate * steps.tech_writer_level_steps[zone][level - 1], 2)
    elif title == 'Recruiting':
        return round(rate * steps.recruiting_level_steps[zone][level - 1], 2)
    elif title == 'Data Science' or title == 'Tech Ops':
        return round(rate * steps.data_science_tech_ops_level_steps[zone][level - 1], 2)
    elif title == 'Tech Support':
        return round(rate * steps.tech_support_level_steps[zone][level - 1], 2)
    else:
        return round(rate * steps.level_steps[zone][level - 1], 2)


def bigStepper(level, zone, rate, title):
    starter_rate = zoneStepper(zone - 1, rate, title)
    return levelStepper(level, zone, starter_rate, title)
