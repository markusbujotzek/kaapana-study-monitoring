
const settings = {
    darkMode: true,
    navigationMode: false,
    landingPage: ['Patient Sex', 'Modality'],
    datasets: {
        structured: false,
        cols: 'auto',
        cardText: true,
        tagBar: {
            multiple: false,
            tags: []

        },
        itemsPerPagePagination: 1000,
        sort: "00000000 TimestampArrived_datetime",
        sortDirection: "desc",
        executeSlicedSearch: false,
        props: [
            {
                name: 'Series Description',
                display: true,
                truncate: true,
                dashboard: false,
                patientView: false,
                studyView: false
            },
            {
                name: 'Patient ID',
                display: false,
                truncate: true,
                dashboard: false,
                patientView: false,
                studyView: false
            },
            {
                name: 'Patient Name',
                display: true,
                truncate: true,
                dashboard: false,
                patientView: true,
                studyView: false
            },
            {
                name: 'Patient Birth Date',
                display: false,
                truncate: true,
                dashboard: false,
                patientView: true,
                studyView: false
            },
            {
            name: 'Patient Sex',
                display: true,
                truncate: true,
                dashboard: false,
                patientView: true,
                studyView: false
            },
            {
                name: 'Study Description',
                display: true,
                truncate: true,
                dashboard: false,
                patientView: false,
                studyView: false
            },
            {
                name: 'Study Date',
                display: true,
                truncate: true,
                dashboard: false,
                patientView: false,
                studyView: true
            },
            {
                name: 'Modality',
                display: false,
                truncate: false,
                dashboard: true,
                patientView: true,
                studyView: true
            },
            {
                name: 'Tags',
                display: false,
                truncate: false,
                dashboard: true,
                patientView: false,
                studyView: false
            },
            {
                name: 'Manufacturer',
                display: false,
                truncate: false,
                dashboard: true,
                patientView: false,
                studyView: false
            }
        ]
    },
    workflows: {
        /*
        [dagName]: {
            properties: {
                    [param1_name]: 'param1 value',
                    [param2_name]: 'param2 Value',
            },
            hideOnUI: ['param2_name'],  // param2Name will be hidden on the workflow form in UI       
        }
        */
        validateDicoms: {
            properties: {
                validator_algorithm: 'dciodvfy',
                exit_on_error: false,
                tags_whitelist: [],  
            },
            hideOnUI: ['tags_whitelist'],
        },
    },
}
export {settings}