
from arcgis import GIS
from arcgis.features import GeoAccessor
from arcgis.features import GeoSeriesAccessor
import pandas as pd

# original number of microzones
count_previous = 26050
count_previous_sl = 10718
count_previous_wbe = 3724
count_previous_da = 3810
count_previous_ut = 7797
count_previous_wfrc = count_previous_sl + count_previous_wbe + count_previous_da


# read in microzones
print('- reading data sources...')
maz_sl = pd.DataFrame.spatial.from_featureclass(r'..\_SaltLake\Inputs\Microzones_DRAFT.gdb\Microzones_DRAFT')
maz_da = pd.DataFrame.spatial.from_featureclass(r'..\_Davis\Inputs\Microzones_DRAFT.gdb\Microzones_DRAFT')
maz_ut = pd.DataFrame.spatial.from_featureclass(r'..\_Utah\Inputs\Microzones_DRAFT.gdb\Microzones_DRAFT')
maz_wbe = pd.DataFrame.spatial.from_featureclass(r'..\_Weber_BoxElder\Inputs\Microzones_DRAFT.gdb\Microzones_DRAFT')
taz_df = pd.DataFrame.spatial.from_featureclass(r'..\_SaltLake\Inputs\TAZ_MAZ_Tracker.shp')
print('- summarizing progress...\n')

# filter to respective counties
maz_sl = maz_sl[(maz_sl['CO_FIPS']==35)].copy()
maz_da = maz_da[(maz_da['CO_FIPS']==11)].copy()
maz_ut = maz_ut[(maz_ut['CO_FIPS']==49)].copy()
maz_wbe = maz_wbe[(maz_wbe['CO_FIPS'].isin([3,57]))].copy()

# get total number of microzones
n_maz_sl = maz_sl.shape[0]
n_maz_da = maz_da.shape[0]
n_maz_ut = maz_ut.shape[0]
n_maz_wbe = maz_wbe.shape[0]
total_maz = n_maz_sl + n_maz_da + n_maz_ut + n_maz_wbe

# get total unique TAZ IDs that have been reviewed (Status=1)
maz_sl_reviewed = maz_sl[(maz_sl['Status']==1)].copy()
maz_da_reviewed = maz_da[(maz_da['Status']==1)].copy()
maz_ut_reviewed = maz_ut[(maz_ut['Status']==1)].copy()
maz_wbe_reviewed = maz_wbe[(maz_wbe['Status']==1)].copy()

n_taz_ids_sl = len(maz_sl_reviewed['SA_TAZID'].unique())
n_taz_ids_da = len(maz_da_reviewed['SA_TAZID'].unique())
n_taz_ids_ut = len(maz_ut_reviewed['SA_TAZID'].unique())
n_taz_ids_wbe = len(maz_wbe_reviewed['SA_TAZID'].unique())

# count unique MAZs
count_sl_maz = maz_sl_reviewed.shape[0]
count_da_maz = maz_da_reviewed.shape[0]
count_ut_maz = maz_ut_reviewed.shape[0]
count_wbe_maz = maz_wbe_reviewed.shape[0]
count_wfrc_maz = count_sl_maz + count_da_maz + count_wbe_maz
count_all_maz = count_sl_maz + count_da_maz + count_ut_maz + count_wbe_maz

# sum reviewed taz ids
total_taz_ids = n_taz_ids_sl + n_taz_ids_da + n_taz_ids_ut + n_taz_ids_wbe
total_wfrc_taz_ids = n_taz_ids_sl + n_taz_ids_da  + n_taz_ids_wbe

# get total number of TAZ
wfrc_taz = taz_df[taz_df['CO_FIPS'].isin([35,11,3,57])].copy()
sl_taz = taz_df[taz_df['CO_FIPS'].isin([35])].copy()
da_taz = taz_df[taz_df['CO_FIPS'].isin([11])].copy()
wbe_taz = taz_df[taz_df['CO_FIPS'].isin([57,3])].copy()
mag_taz = taz_df[taz_df['CO_FIPS'].isin([49])].copy()
count_taz = taz_df.shape[0]
count_wfrc_taz = wfrc_taz.shape[0]
count_sl_taz = sl_taz.shape[0]
count_da_taz = da_taz.shape[0]
count_wbe_taz = wbe_taz.shape[0]
count_mag_taz = mag_taz.shape[0]

# print stuff
print('MAZ Delineation Summary')
print('-'*30)
print(f'Original number of microzones: {count_previous}')
print(f'Current number of microzones: {total_maz}')
print(f'Current number of APPROVED microzones: {count_all_maz}')
print('-'*30)
print(f'Total number of TAZs reviewed: {total_taz_ids} out of {count_taz} ({round(total_taz_ids/count_taz*100)}%)')
print('\n')
print(f'Total number of WFRC TAZs reviewed: {total_wfrc_taz_ids} out of {count_wfrc_taz} ({round(total_wfrc_taz_ids/count_wfrc_taz*100)}%)')
print(f'-- Estimated hours remaining: {round(((count_wfrc_taz - total_wfrc_taz_ids) * 8)/60)} hours')
print(f'-- Current number of microzones: {count_wfrc_maz}')
print(f'-- Original number of microzones: {count_previous_wfrc}')
print('\n')

print(f'Total number of Box Elder/Weber TAZs reviewed: {n_taz_ids_wbe} out of {count_wbe_taz} ({round(n_taz_ids_wbe/count_wbe_taz*100)}%)')
print(f'-- Estimated hours remaining: {round(((count_wbe_taz - n_taz_ids_wbe) * 8)/60)} hours')
print(f'-- Current number of microzones: {count_wbe_maz}')
print(f'-- Original number of microzones: {count_previous_wbe}')
print('\n')

print(f'Total number of Davis TAZs reviewed: {n_taz_ids_da} out of {count_da_taz} ({round(n_taz_ids_da/count_da_taz*100)}%)')
print(f'-- Estimated hours remaining: {round(((count_da_taz - n_taz_ids_da) * 8)/60)} hours')
print(f'-- Current number of microzones: {count_da_maz}')
print(f'-- Original number of microzones: {count_previous_da}')
print('\n')

print(f'Total number of Salt Lake TAZs reviewed: {n_taz_ids_sl} out of {count_sl_taz} ({round(n_taz_ids_sl/count_sl_taz*100)}%)')
print(f'-- Estimated hours remaining: {round(((count_sl_taz - n_taz_ids_sl) * 8)/60)} hours')
print(f'-- Current number of microzones: {count_sl_maz}')
print(f'-- Original number of microzones: {count_previous_sl}')
print('\n')

print(f'Total number of MAG TAZs reviewed: {n_taz_ids_ut} out of {count_mag_taz} ({round(n_taz_ids_ut/count_mag_taz*100)}%)')
print(f'-- Estimated hours remaining: {round(((count_mag_taz - n_taz_ids_ut) * 8)/60)} hours')
print(f'-- Current number of microzones: {count_ut_maz}')
print(f'-- Original number of microzones: {count_previous_ut}')
print('\n')

del maz_sl
del maz_da
del maz_ut
del maz_wbe
del taz_df