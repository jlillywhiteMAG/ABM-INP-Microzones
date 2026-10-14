from pathlib import Path

import geopandas as gpd


COUNT_PREVIOUS_UT = 9765
UTAH_COUNTY_FIPS = 49
MINUTES_PER_TAZ = 8
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
MAZ_PATH = REPOSITORY_ROOT / '_Utah' / 'Inputs' / 'Microzones_DRAFT.gdb'
TAZ_PATH = REPOSITORY_ROOT / '_SaltLake' / 'Inputs' / 'TAZ_MAZ_Tracker.shp'


print('- reading Utah County data sources...')
maz_df = gpd.read_file(MAZ_PATH, layer='Microzones_DRAFT')
taz_df = gpd.read_file(TAZ_PATH)

maz_utah = maz_df.loc[maz_df['CO_FIPS'] == UTAH_COUNTY_FIPS]
taz_utah = taz_df.loc[taz_df['CO_FIPS'] == UTAH_COUNTY_FIPS]
maz_reviewed = maz_utah.loc[maz_utah['Status'] == 1]

current_maz_count = len(maz_utah)
approved_maz_count = len(maz_reviewed)
reviewed_taz_count = maz_reviewed['SA_TAZID'].nunique()
total_taz_count = len(taz_utah)
percent_reviewed = round(reviewed_taz_count / total_taz_count * 100)
hours_remaining = round((total_taz_count - reviewed_taz_count) * MINUTES_PER_TAZ / 60)

print('\nUtah County MAZ Delineation Summary')
print('-' * 35)
print(f'TAZs reviewed: {reviewed_taz_count} out of {total_taz_count} ({percent_reviewed}%)')
print(f'Estimated hours remaining: {hours_remaining} hours')
print(f'Current number of microzones: {current_maz_count}')
print(f'Approved microzones: {approved_maz_count}')
print(f'Original number of microzones: {COUNT_PREVIOUS_UT}')
