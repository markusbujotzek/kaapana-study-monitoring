from datetime import timedelta
from kaapana.operators.KaapanaPythonBaseOperator import KaapanaPythonBaseOperator
import requests
from glob import glob
from os.path import join, basename, dirname, exists, realpath
import json
import re


class LocalPushToPromOperator(KaapanaPythonBaseOperator):
    site_geo_data_dict = None

    def set_defaults(self, parsed_data):
        geo_data_json_path = join(dirname(realpath(__file__)), "geo_data.json")
        with open(geo_data_json_path, "r") as file:
            site_geo_list = json.load(file)

        for geo_data in site_geo_list:
            id = geo_data["id"]
            city = geo_data["city"]
            full_name = geo_data["full_name"]
            lat = geo_data["lat"]
            lon = geo_data["lon"]
            instance_name = f"{id}-{city}"

            if "UKMI".lower() in instance_name.lower():
                continue

            if instance_name not in parsed_data:
                try:
                    print(f"Searching for last timestamp of: {instance_name}")
                    payload = {
                        "query": f'max_over_time(instance_info{{instance="{instance_name}"}}[24h])'
                    }
                    response = requests.get(
                        self.prometheus_url,
                        timeout=self.timeout,
                        params=payload,
                        verify=self.verify_ssl,
                    )
                    timestamp = 0
                    for result in response.json()["data"]["result"]:
                        value = int(result["value"][1])
                        timestamp = value if value > timestamp else timestamp

                except Exception as e:
                    print("Error with prometeus request: ")
                    print(e)
                    print(f"Setting timestamp = 0 for {instance_name} ")
                    timestamp = 0

                parsed_data[instance_name] = {
                    f"{timestamp}": {
                        "instance_info": f'# HELP instance_info site information.\n# TYPE instance_info gauge\ninstance_info{{instance_id="{id}",full_name="{full_name}",city="{city}",longitude="{lon}",latitude="{lat}"}} {timestamp}\n',
                    }
                }
        return parsed_data

    def split_metrics_projects(self, metrics_all_projects):
        """
        Splits the provided metrics by project.

        :param metrics_all_projects: Dictionary containing metric data.
        :return: Dictionary where keys are project names and values contain filtered metrics.
        """
        # Identify projects by extracting unique `trial_short_code` values
        project_pattern = re.compile(r'trial_short_code="(.*?)"')
        projects = set()

        for key, value in metrics_all_projects.items():
            projects.update(project_pattern.findall(value))

        if len(projects) > 0:
            # Create a dictionary to store filtered metrics per project
            project_metrics = {project: {} for project in projects}
        else:
            # no project-specific metrics info available for current site -> keep default data
            project_metrics = {"project_dummy": metrics_all_projects}

        # Iterate over each project and filter relevant metrics
        for project in projects:
            for key, value in metrics_all_projects.items():
                filtered_lines = []

                # Keep only lines that either belong to the project or don't contain `trial_short_code`
                for line in value.split("\n"):
                    if (
                        f'trial_short_code="{project}"' in line
                        or "trial_short_code=" not in line
                    ):
                        filtered_lines.append(line)

                # Store filtered metrics
                project_metrics[project][key] = "\n".join(filtered_lines)

        return project_metrics

    def retrieve_projects(self, prom_updates):
        # Identify projects by extracting unique `trial_short_code` values
        project_pattern = re.compile(r'trial_short_code="(.*?)"')
        projects = set()

        for site, site_data in prom_updates.items():
            for site_timestamp, site_timestamp_data in site_data.items():
                for job_name, job_data in site_timestamp_data.items():
                    projects.update(project_pattern.findall(job_data))

        return projects

    def push_to_gateway(self, project_pushgateway_url, job_name, instance_name, data):
        headers = {"X-Requested-With": "Python requests", "Content-type": "text/xml"}
        url = (
            f"{project_pushgateway_url}/metrics/job/{job_name}/instance/{instance_name}"
        )
        assert job_name != None
        job_name = job_name.strip().replace(" ", "-")
        assert instance_name != None
        print(f"Pushing {job_name=} {instance_name=} to {url=}!")
        try:
            response = requests.post(
                url,
                headers=headers,
                data=data.encode("utf-8"),
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
        except requests.exceptions.Timeout:
            print("Post request error! - Timeout")
        except requests.exceptions.TooManyRedirects:
            print("Post request error! - TooManyRedirects")
            exit(1)
        except requests.exceptions.RequestException as e:
            print("Post request error! - RequestException")
            print(str(e))
            # exit(1)
            print(
                f"ERROR: Ensure that study Monitoring is installed for all projects, especially for respective project with {project_pushgateway_url=} !"
            )
            return

        if response.status_code != 200:
            print(f"# ERROR! Status code: {response.status_code}!")
            print(f"# Text: {response.text}!")
            exit(1)
        elif response.status_code == 200:
            print("Request was ok!")
            print(response.text)

    def start(self, ds, **kwargs):
        global INSTANCE_NAME
        print("Start LocalPushToPromOperator ...")
        conf = kwargs["dag_run"].conf
        run_dir = join(self.airflow_workflow_dir, kwargs["dag_run"].run_id)
        batch_folder = [f for f in glob(join(run_dir, self.batch_name, "*"))]

        prom_updates = {}
        for batch_element_dir in batch_folder:
            element_input_dir = join(batch_element_dir, self.operator_in_dir, "*.txt")
            print(f"# Searching for metrics.txt files in {element_input_dir}")
            aggregated_metrics_files = sorted(glob(element_input_dir, recursive=False))
            print(f"# Found {len(aggregated_metrics_files)} txt files.")

            for aggregated_metrics_file in aggregated_metrics_files:
                print(f"Prepare metrics from: {aggregated_metrics_file}")

                job_name = None
                instance_name = None
                timestamp = None
                metrics_data = ""
                with open(aggregated_metrics_file, "r", encoding="utf-8") as file:
                    for line in file:
                        line_text = line.rstrip()
                        print(f"{line_text=}")
                        if "instance_name:" in line_text:
                            instance_name = line_text.split("instance_name:")[
                                -1
                            ].strip()
                            print(f"{instance_name=}")
                            if instance_name not in prom_updates:
                                prom_updates[instance_name] = {}
                        elif "version:" in line_text:
                            version = line_text.split("version:")[-1].strip()
                            print(f"{version=}")
                        elif "timestamp:" in line_text:
                            timestamp = line_text.split("timestamp:")[-1].strip()
                            print(f"{timestamp=}")
                            assert instance_name != None
                            if timestamp not in prom_updates[instance_name]:
                                prom_updates[instance_name][timestamp] = {}
                        elif "job_name:" in line_text:
                            job_name = line_text.split("job_name:")[-1].strip()
                            print(f"{job_name=}")
                            if (
                                metrics_data != ""
                                and job_name
                                not in prom_updates[instance_name][timestamp]
                            ):
                                prom_updates[instance_name][timestamp][
                                    job_name
                                ] = metrics_data
                            metrics_data = ""
                        else:
                            metrics_data += f"{line_text}\n"

        prom_updates = self.set_defaults(parsed_data=prom_updates)
        print("PROM UPDATES!")
        print(prom_updates)
        print(json.dumps(prom_updates, indent=4, ensure_ascii=False))

        # get all projects that are included in prom_updates
        projects = self.retrieve_projects(prom_updates)
        print(f"We found the following available projects: {projects=}")

        for instance_name, timestamp_data in prom_updates.items():
            print(f"Processing: {instance_name=}")
            count_data_items = len(timestamp_data.keys())
            assert count_data_items != 0
            if count_data_items > 1:
                print(f"# Found multiple timestamps {timestamp_data.keys()}")
                latest_timestamp = sorted(timestamp_data.keys())[-1]
                print(f"# selected {latest_timestamp=}")
                timestamp_data = timestamp_data[latest_timestamp]
            else:
                timestamp_data = timestamp_data[next(iter(timestamp_data))]

            # split metrics in timestamp_data w.r.t. trial_short_code (= project name)
            project_specific_metrics = self.split_metrics_projects(timestamp_data)

            for project_name in projects:
                # compose project-specific pushgateway_url
                # _project_name = project_name.replace("project_", "")
                project_pushgateway_url = self.pushgateway_url.replace(
                    "pgateway-service", f"pgateway-service-{project_name}", 1
                )

                # take project-specific metrics data of current instance if available or "project_dummy" data if not available
                current_project_specific_metrics = (
                    project_specific_metrics[project_name]
                    if project_name in project_specific_metrics
                    else project_specific_metrics["project_dummy"]
                )
                for job_name, metrics_data in current_project_specific_metrics.items():
                    print(f"DEF START() {job_name=}")
                    print(f"DEF START() {metrics_data=}")
                    self.push_to_gateway(
                        project_pushgateway_url=project_pushgateway_url,
                        job_name=job_name,
                        instance_name=instance_name,
                        data=metrics_data,
                    )

    def __init__(
        self,
        dag,
        # pushgateway_url used to push the metrics; to be adapted according to available projects
        pushgateway_url="http://pgateway-service.services.svc:9091",
        # prometheus_url only used to find from own instance the uptime -> get info per default form project "admin"
        prometheus_url="http://prom-mon-service-admin.services.svc:9090/prom-monitoring/api/v1/query",
        timeout=5,
        verify_ssl=False,
        **kwargs,
    ):
        self.pushgateway_url = pushgateway_url
        self.prometheus_url = prometheus_url
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        super().__init__(
            dag=dag,
            name="push-metrics-to-prometheus",
            python_callable=self.start,
            **kwargs,
        )
