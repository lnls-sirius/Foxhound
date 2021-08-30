import asyncio
import aiohttp
import operator
import pandas as pd
from datetime import datetime, timedelta
import requests
import ast

class EPICS_Requests:

    def __init__(self):
        self.PVS_URL = 'http://10.0.38.42/mgmt/bpl/getAllPVs'
        self.ARCHIVE_URL = 'http://10.0.38.42/retrieval/data/getData.json'
        self.data = pd.DataFrame(data={'datetime': [], 'pv': []})

    def get_names(self, regex=None, limit=100):
        if(regex == None):
            params = {'limit': limit}
        else:
            params = {'limit': limit, 'regex':regex}

        response = requests.get(self.PVS_URL, params=params, verify=False)

        return ast.literal_eval(response.text)

    def  get_pv(self, pv_list, dt_init, dt_end):
        if(dt_init != None and dt_end != None):
            dt_init = (dt_init - dt_init.utcoffset()).replace(tzinfo=None).isoformat(timespec='milliseconds')+'Z'
            dt_end = (dt_end - dt_end.utcoffset()).replace(tzinfo=None).isoformat(timespec='milliseconds')+'Z'
            timespam = {"init": dt_init, "end": dt_end}
            time = True
        else:
            time = False
            print('Erro com os tempos!')
        
        optimize = True
        mean_minutes = 3
        
        res = []

        for pv in pv_list:
    
            if optimize:
                pv_query = f'mean_{int(60*mean_minutes)}({pv})'
            else:
                pv_query = pv
            if(time == True):
                query = {'pv': pv_query, 'from': dt_init, 'to': dt_end}
            else:
                query = {'pv': pv_query}
            response_as_json = {}
            res.append(requests.get(self.ARCHIVE_URL, params=query).json())

        res_mapped = list(map(lambda x: x[0]['data'], res))

        values = [list(map(lambda x: x['val'], pv_data)) for pv_data in res_mapped]
        ts = [list(map(lambda x: datetime.fromtimestamp(x['secs']).strftime("%d.%m.%y %H:%M"), pv_data)) for pv_data in res_mapped]
        # creating pandas dataframe object
        d = {'datetime': ts[0]}
        for val, pv in zip(values, pv_list):
            d[pv] = val
        self.data = pd.DataFrame(data=d)
        # indexing by datetime
        self.data.reset_index(drop=True, inplace=True)
        self.data = self.data.set_index('datetime')

        return self.data

    async def fetch(self, session, pv, time_from, time_to, is_optimized, mean_minutes):
        if is_optimized:
            pv_query = f'mean_{int(60*mean_minutes)}({pv})'
        else:
            pv_query = pv
        query = {'pv': pv_query, 'from': time_from, 'to': time_to}
        response_as_json = {}
        async with session.get(self.ARCHIVE_URL, params=query) as response:
            try:
                response_as_json = await response.json()
            except aiohttp.client_exceptions.ContentTypeError:
                print(f'Failed to retrieve data from PV {pv}.')
                response_as_json = None
            return response_as_json


    async def retrieve_data(self, pvs, time_from, time_to, isOptimized=False, mean_minutes=0):
        async with aiohttp.ClientSession() as session:
            self.data = await asyncio.gather(*[self.fetch(session, pv, time_from, time_to, isOptimized, mean_minutes) for pv in pvs])
            return self.data


    async def fetch_data(self, pv_list, timespam):
        optimize = True
        mean_minutes = 3
        res = await self.retrieve_data(pv_list, timespam['init'], timespam['end'], optimize, mean_minutes)
        try:
            # cleaning response
            res_mapped = list(map(lambda x: x[0]['data'], res))
        except TypeError:
            log.append_stdout('Incorrect PV(s) name(s) or bad timespam. Fetching failed.\n')
            return
        values = [list(map(lambda x: x['val'], pv_data)) for pv_data in res_mapped]
        ts = [list(map(lambda x: datetime.fromtimestamp(x['secs']).strftime("%d.%m.%y %H:%M"), pv_data)) for pv_data in res_mapped]
        # creating pandas dataframe object
        d = {'datetime': ts[0]}
        for val, pv in zip(values, pv_list):
            d[pv] = val
        self.data = pd.DataFrame(data=d)
        # indexing by datetime
        self.data.reset_index(drop=True, inplace=True)
        self.data = data.set_index('datetime')
        
        return self.data

    def call_fetch(self, pv_list, dt_init, dt_end):
        try:
            dt_init = (dt_init - dt_init.utcoffset()).replace(tzinfo=None).isoformat(timespec='milliseconds')+'Z'
            dt_end = (dt_end - dt_end.utcoffset()).replace(tzinfo=None).isoformat(timespec='milliseconds')+'Z'
            timespam = {"init": dt_init, "end": dt_end}
        except:
            print('Erro com os tempos!')
            return
        
        asyncio.create_task(self.fetch_data(pv_list, timespam))
