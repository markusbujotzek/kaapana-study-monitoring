import logging
import re
from typing import Dict, List

import requests
from fastapi import HTTPException
from opensearchpy import OpenSearch
import math
from app.config import settings
from app.workflows.utils import (
    requests_retry_session,
    TIMEOUT,
    raise_kaapana_connection_error,
)
from app.logger import get_logger
#Opensearch values (defaults)
MAX_RETURN_LIMIT = 10000
MAX_SLICES_PER_PIT = 1024
logger = get_logger(__name__, logging.DEBUG)


#  from kaapana.operators.HelperOpensearch import HelperOpensearch
# Function to create a PIT
def create_pit(index, keep_alive='1m'):
    response = OpenSearch(
            hosts=f"opensearch-service.{settings.services_namespace}.svc:9200"
        ).create_pit(index=index, keep_alive=keep_alive)
    return response['pit_id']

# Function to close a PIT
def close_pit(pit_id):
    OpenSearch(
            hosts=f"opensearch-service.{settings.services_namespace}.svc:9200"
        ).delete_pit(body={'pit_id': pit_id})

# Function to execute a search with slicing
def execute_sliced_search(query, pit_id, aggregated_series_num, page_index, source=False, sort=[{"0020000E SeriesInstanceUID_keyword.keyword": "desc"}], size=1000):  
    total_slices = math.ceil(aggregated_series_num / size)
    slice_id = page_index - 1
    # total_slices is limited by MAX_SLICES_PER_PIT
    if total_slices >= MAX_SLICES_PER_PIT:
        total_slices = MAX_SLICES_PER_PIT
        size = math.ceil(aggregated_series_num / total_slices)
        if size > MAX_RETURN_LIMIT:
            size = MAX_RETURN_LIMIT
    
    body = {
        "query": query,
        "_source": source,
        "sort": sort,
        "size": size,
        "pit": {"id": pit_id, "keep_alive": "1m"},
        "slice": {"id": slice_id, "max": total_slices}
    }
    res = OpenSearch(
            hosts=f"opensearch-service.{settings.services_namespace}.svc:9200"
        ).search(body=body)
    # import debugpy
    # debugpy.listen(("localhost", 17777))
    # debugpy.wait_for_client()
    # debugpy.breakpoint()

    return res["hits"]["hits"]

def execute_from_size_search(
    query: Dict = dict(),
    source=False,
    index="meta-index",
    sort=[{"0020000E SeriesInstanceUID_keyword.keyword": "desc"}],
    start_from=1,
    size=1000,
) -> List:
    """
    Opensearch size limit is 10000 MAX_RETURN_LIMIT.
    If you want to query more, this function has to be called again,
    otherwise the response will time out.
    Caution: Removing or adding entries between requests will lead to inconsistencies.
    Opensearch offers the 'scroll' functionality which prevents this, but creating
    the required sessions takes too much time for most requests.
    Therefore, it is not implemented.

    :param query: query to execute
    :param source: opensearch _source parameter
    :param index: index on which to execute the query
    :param sort: sort the results
    :param start_from: the result start from
    :param size: the result size
    :return: aggregated search results
    """
    start_from = (start_from - 1) * size
<<<<<<< HEAD
    # limit size to 10000 (opensearch maximum)
    if size > 10000:
        size = 10000
    res = os_client.search(
=======

    res = OpenSearch(
        hosts=f"opensearch-service.{settings.services_namespace}.svc:9200"
    ).search(
>>>>>>> 6fa1a1c27 (introduce PIT slicing seach and seach_after)
        body={
            "from": start_from,
            "query": query,
            "size": size,
            "_source": source,
            "sort": sort,
        },
        index=index,
    )
    return res["hits"]["hits"]

def execute_search_after_search(
    pit_id,
    query: Dict = dict(),
    source=False,
    sort=[{"0020000E SeriesInstanceUID_keyword.keyword": "desc"}],
    start_from=1,
    size=1000,
) -> List:
    """
    Execute a search query using the search_after parameter for pagination.
    
    :param query: Query to execute
    :param source: OpenSearch _source parameter
    :param index: Index on which to execute the query
    :param sort: Sort the results
    :param start_from: The result start from (page number)
    :param size: The result size (number of results per page)
    :return: Aggregated search results
    """
    def _execute_search_after(selected_size, _source=False, search_after=None):
        body = {
            "query": query,
            "_source": _source,
            "sort": sort + [{"_id": "asc"}],  #add _id for unique search, otherwise search_after could sort after missing values.
            "size": selected_size,
            "pit": {"id": pit_id, "keep_alive": "1m"},
        }
        if search_after:
            body["search_after"] = search_after

        res = OpenSearch(
                hosts=f"opensearch-service.{settings.services_namespace}.svc:9200"
            ).search(body=body)
        return res
    search_after = None
    start_from = (start_from - 1) * size
    search_before = math.floor(start_from/MAX_RETURN_LIMIT)

    for _ in range(search_before):
        response = _execute_search_after(selected_size=MAX_RETURN_LIMIT,  search_after=search_after)
        hits = response['hits']['hits']
        if not hits:
            break
        search_after = hits[-1]['sort']

    #diff between selected page and hit count: 
    missing = start_from - search_before*MAX_RETURN_LIMIT
    if missing > 0:
        response = _execute_search_after(selected_size=missing, search_after=search_after)
        hits = response['hits']['hits']
        if hits:
            search_after = hits[-1]['sort']

    #the final actuall wanted results including _source value        
    response = _execute_search_after(selected_size=size, _source=source, search_after=search_after)
    
    return response["hits"]["hits"]

def execute_initial_search(query, source, sort, page_index, page_length, aggregated_series_num, use_execute_sliced_search):
    # for results len below 10000 use directly from, size    
    if aggregated_series_num < MAX_RETURN_LIMIT:
        hits = execute_from_size_search(
            query=query,
            source=source,
            sort=sort,
            start_from=page_index,
            size=page_length,
        )    
    else:
        # Create a PIT
        pit_id = create_pit(index="meta-index")
        #initially only the patitenid is needed, for resorting later
        patient_source = {
                "includes": [
                    "00100020 PatientID_keyword",
                ]
            }
        #faster, but only each slide/page is sorted, not all slides.    
        if use_execute_sliced_search:
            hits = execute_sliced_search(
                query=query,
                source=patient_source,
                page_index=page_index,
                sort=sort,
                pit_id=pit_id,
                aggregated_series_num=aggregated_series_num,
                size=page_length,
            )
        else:
            hits = execute_search_after_search(
            query=query,
            source=patient_source,
            sort=sort,
            pit_id=pit_id,
            start_from=page_index,
            size=page_length,
        ) 
        close_pit(pit_id)
    return hits

def requery_for_patients(query, source, sort, page_length, hits):
    '''
    The initial search result list() is sorted depending on the sort value. So the result
    does not contain every result for the indiviual patients. Therefore if structured 
    (and sorted patient depending)
    the results have to be requeried, with the same query but individual for this page patients
    '''
    patients = list({hit['_source'].get('00100020 PatientID_keyword', 'N/A') for hit in hits})
    #remove duplicates but keep order
    selected_patients = list(dict.fromkeys(patients))
    print("selected_patients", len(selected_patients))
    print("hits", len(hits))
    final_hits = [] 
    for patient in selected_patients:
        #filter for the individual patients of this page only
        patient_query = {
            "bool": {
                "must": [query],
                "filter": [{"term": {"00100020 PatientID_keyword": patient}}],
            }
        }
        patient_hits = execute_from_size_search(
            query=patient_query,
            source=source,
            sort=sort,
            start_from=1,
            size=page_length,
        )
        #be aware that final_hits >= page_length, since all patients part of initial
        #call are added. But this prevents not seeing every patient when switching pages
        # but patients at the end of one page could also be shown on the next page.
        final_hits.extend(patient_hits)

    print("final_hits", len(final_hits))
    return final_hits

def contains_numbers(s):
    return bool(re.search(r"\d", s))


def camel_case_to_space(s):
    removed_tag = s.split(" ")[-1]
    removed_type = removed_tag.split("_")[0]

    res = " ".join(
        re.sub(
            "([A-Z][a-z]+)",
            r" \1",
            re.sub(
                "([A-Z]+)",
                r" \1",
                removed_type,
            ),
        ).split()
    )
    return res


def type_suffix(v):
    if "type" in v:
        type_ = v["type"]
        return "" if type_ != "text" and type_ != "keyword" else ".keyword"
    else:
        return ""


async def get_metadata_opensearch(os_client, series_instance_uid: str) -> dict:
    data = os_client.get(index="meta-index", id=series_instance_uid)["_source"]

    # filter for dicoms tags
    return {
        # camel_case_to_space(key): dict(value=value, tag=["0000", "0000"])
        camel_case_to_space(key): value
        for key, value in data.items()
        if key != ""
    }


async def get_metadata(os_client, series_instance_uid: str) -> Dict[str, str]:
    # TODO: retrieve study_instance_uid using meta-index
    # pacs_metadata: dict = await get_metadata_pacs(
    #     study_instance_uid, series_instance_uid
    # )
    opensearch_metadata: dict = await get_metadata_opensearch(
        os_client, series_instance_uid
    )

    # return {**pacs_metadata, **opensearch_metadata}
    return opensearch_metadata


async def get_metadata_pacs(study_instance_UID: str, series_instance_UID: str) -> dict:
    def load_metadata_form_pacs(study_uid, series_uid) -> dict:
        url = (
            f"http://dcm4chee-service.{settings.services_namespace}.svc:8080/dcm4chee-arc/aets/KAAPANA"
            + f"/rs/studies/{study_uid}/series/{series_uid}/metadata"
        )
        with requests.Session() as s:
            http_response = requests_retry_session(retries=5, session=s).get(
                url,
                timeout=TIMEOUT,
            )
            raise_kaapana_connection_error(http_response)

        if http_response.status_code == 200:
            return http_response.json()
        else:
            print("################################")
            print("#")
            print("# Can't request metadata from PACS!")
            print(f"# StudyUID: {study_uid}")
            print(f"# SeriesUID: {series_uid}")
            print(f"# Status code: {http_response.status_code}")
            print(http_response.text)
            print("#")
            print("################################")
            return {}

    try:
        data = load_metadata_form_pacs(study_instance_UID, series_instance_UID)
    except Exception as e:
        print("Exception", e)
        raise HTTPException(500, e)

    from dicom_parser.utils.vr_to_data_element import get_data_element_class
    from pydicom import Dataset

    dataset = Dataset.from_json(data[0])
    parsed_and_filtered_data = [
        get_data_element_class(dataElement)(dataElement)
        for _, dataElement in dataset.items()
        if dataElement.VR != "SQ"
        and dataElement.VR != "OW"
        and dataElement.keyword != ""
    ]

    res = {}
    for d_ in parsed_and_filtered_data:
        value = d_.value
        if d_.VALUE_REPRESENTATION.name == "PN":
            value = "".join([v + " " for v in d_.value.values() if v != ""])
        # res[d_.description] = dict(value=str(value), tag=d_.tag)
        res[d_.description] = str(value)
    return res


async def get_field_mapping(os_client, index="meta-index") -> Dict:
    """
    Returns a mapping of field for a given index form open search.
    This looks like:
    # {
    #   'Specific Character Set': '00080005 SpecificCharacterSet_keyword.keyword',
    #   'Image Type': '00080008 ImageType_keyword.keyword'
    #   ...
    # }
    """
    import re

    res = os_client.indices.get_mapping(index=index)[index]["mappings"]["properties"]

    name_field_map = {
        camel_case_to_space(k): k + type_suffix(v) for k, v in res.items()
    }

    name_field_map = {
        k: v
        for k, v in name_field_map.items()
        if len(re.findall("\d", k)) == 0 and k != "" and v != ""
    }
    return name_field_map
