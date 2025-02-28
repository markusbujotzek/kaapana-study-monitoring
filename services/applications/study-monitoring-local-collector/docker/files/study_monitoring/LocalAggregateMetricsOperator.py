from datetime import timedelta
from kaapana.operators.KaapanaPythonBaseOperator import KaapanaPythonBaseOperator
from os.path import join, exists, dirname, basename, realpath
import os
import time
import json
from glob import glob
import random


class LocalAggregateMetricsOperator(KaapanaPythonBaseOperator):
    site_geo_data_dict = None

    def get_geo_data(self):
        geo_data_json_path = join(dirname(realpath(__file__)), "geo_data.json")
        with open(geo_data_json_path, "r") as file:
            site_geo_list = json.load(file)

        if self.instance_name.lower() == "random":
            random_pick = random.choice(site_geo_list)
            return f"{random_pick['id']}-{random_pick['city']}", random_pick

        instance_id = self.instance_name.split("-")[0].strip().capitalize()
        site_geo_list = [
            x for x in site_geo_list if x["id"].capitalize() == instance_id
        ]
        if len(site_geo_list) == 1:
            return self.instance_name, site_geo_list[0]
        else:
            print(
                "'INSTANCE_NAME' has to follow the style: '<UK_ID> - <City_Name>' eg: 'UKMI - Michelbinge'"
            )
            print(
                "You can find the list of UK_IDs and respective CITY_NAMEs here: https://fdm-git.diz-ag.med.ovgu.de/study/jip/information-model/-/blob/main/representations/information-model.json"
            )
            raise Exception(f"Invalid 'INSTANCE_NAME': {self.instance_name} !")

    def start(self, ds, **kwargs):
        print("Start LocalAggregateMetricsOperator ...")

        run_dir = join(self.airflow_workflow_dir, kwargs["dag_run"].run_id)
        aggregated_metrics_output_dir_path = join(
            run_dir, self.operator_out_dir, "aggregated_metrics.txt"
        )
        os.makedirs(dirname(aggregated_metrics_output_dir_path), exist_ok=True)

        self.instance_name, geo_data = self.get_geo_data()
        unix_time = int(time.time())

        with open(aggregated_metrics_output_dir_path, "w") as aggregated_rest:
            aggregated_rest.write(f"instance_name: {self.instance_name}\n")
            aggregated_rest.write(f"version: {self.version}\n")
            aggregated_rest.write(f"timestamp: {unix_time}\n")
            aggregated_rest.write("# HELP instance_info site information.\n")
            aggregated_rest.write("# TYPE instance_info gauge\n")
            aggregated_rest.write(
                f"instance_info{{instance_id=\"{geo_data['id']}\",full_name=\"{geo_data['full_name']}\",city=\"{geo_data['city']}\",longitude=\"{geo_data['lon']}\",latitude=\"{geo_data['lat']}\"}} {unix_time}\n"
            )
            aggregated_rest.write("job_name: instance_info\n")
            for metric_input_dir in self.input_dirs:
                component_input_dir = join(
                    self.airflow_workflow_dir,
                    kwargs["dag_run"].run_id,
                    metric_input_dir,
                )
                print(f" Searching in componend-dir: {component_input_dir}")
                assert exists(component_input_dir)

                txt_files = glob(join(component_input_dir, "*.txt*"))
                print(f" Found {len(txt_files)} metric txt-files")

                for txt_file in txt_files:
                    print(f"Prepare metrics from: {txt_file}")
                    with open(txt_file) as file:
                        for line in file:
                            aggregated_rest.write(line)
                    aggregated_rest.write(
                        f"job_name: {basename(txt_file).split('.')[0]}\n"
                    )

    def __init__(self, dag, metrics_operators, instance_name, version, **kwargs):
        self.input_dirs = [x.operator_out_dir for x in metrics_operators]
        self.instance_name = instance_name
        self.version = version
        super().__init__(
            dag=dag, name="aggregate-metrics", python_callable=self.start, **kwargs
        )
