# WARNING: Do not run this. It will take forever

import json
import csv
import os
import shutil
import sys
import requests
import argparse


output_dir = './output_r'
reports_dir = "{}/{}".format(output_dir, 'reports')
violations_dir = "{}/{}".format(output_dir, 'violations')
remediations_dir = "{}/{}".format(output_dir, 'remediations')

iqapi = 'api/v2'



def init():

    global iqurl, iquser, iqpwd

    parser = argparse.ArgumentParser(description='Manage your Nexus IQ tokens')

    parser.add_argument('-s', '--server', default='http://localhost:8070', help='', required=False)
    parser.add_argument('-u', '--user', default='admin', help='', required=False)
    parser.add_argument('-p', '--passwd', default='admin123', required=False)
    
    args = vars(parser.parse_args())

    iqurl = args['server']
    iquser = args['user']
    iqpwd = args['passwd']

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    os.mkdir(output_dir)
    os.mkdir(reports_dir)
    os.mkdir(violations_dir)
    os.mkdir(remediations_dir)

    return



def get_application_name(urlPath):
    l = urlPath.split('/')
    return(l[3])



def to_json_file(json_file, json_data):
    json_formatted = json.dumps(json_data, indent=2)

    with open(json_file, 'w') as outfile:
        json.dump(json_data, outfile, indent=2)

    print(json_file)

    return



def to_csv_file(csvFile, csvHeader, csvData):
    with open(csvFile, 'w') as fd:
        fd.write(csvHeader)
        for line in csvData:
            fd.write(line)
    # print(csvFile)
    return



def get_nexusiq_data(end_point):
    url = "{}/{}" . format(iqurl, end_point)
    # print(url)

    req = requests.get(url, auth=(iquser, iqpwd), verify=False)

    if req.status_code == 200:
        res = req.json()
    else:
        print(url)
        print("Error fetching data")
        print ("Exiting...")
        sys.exit()

    return res



def get_nexusiq_data_with_payload(end_point, payload):
    url = "{}/{}" . format(iqurl, end_point)
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}

    req = requests.post(url,
                        headers=headers,
                        allow_redirects = False,
                        json=payload,
                        auth=requests.auth.HTTPBasicAuth(iquser, iqpwd),
                        verify=False)

    if req.status_code == 200:
        res = req.json()
    else:
        print(url)
        print(payload)
        print("Error fetching data")
        print ("Exiting...")
        sys.exit()

    return res



def get_all_applications():
    # https://help.sonatype.com/iqserver/automating/rest-apis/report-related-rest-apis---v2#ReportrelatedRESTAPIsv2-GetapplicationIDStep1-GettheApplicationID

    output_file = "{}/{}.json".format(output_dir, 'all_applications')
    all_applications = get_nexusiq_data('api/v2/applications')
    to_json_file(output_file, all_applications)
    return all_applications



def get_evaluation_reports(data):
    # https://help.sonatype.com/iqserver/automating/rest-apis/report-related-rest-apis---v2

    reports_api = 'api/v2/reports/applications'

    applications = data["applications"]

    for application in applications:
        application_info = {}

        application_info['application_id'] = application["id"]
        application_info['public_id'] = application["publicId"]
        application_info['name'] = application["name"]
        application_info['organization_id'] = application["organizationId"]

        application_info['public_id'] = application["publicId"].replace(" ", "_")
        application_info['name'] = application["name"].replace(" ", "_")

        # https://help.sonatype.com/iqserver/automating/rest-apis/report-related-rest-apis---v2#ReportrelatedRESTAPIsv2-reportId
        end_point = "{}/{}" . format(reports_api, application_info['application_id'])

        output_file = "{}/{}_{}.json".format(reports_dir, application_info['name'], 'reports')
        evaluation_reports = get_nexusiq_data(end_point)

        # Append the application information to the reports info returned from IQ
        final_json = get_final_json(evaluation_reports, application_info)

        to_json_file(output_file, final_json)

    return



def get_final_json(evaluation_report_info, application_info):
    obj = {}

    obj['evaluation_reports'] = evaluation_report_info
    obj['application_info'] = application_info

    return obj



def get_policy_violations():

    for application_file in os.listdir(reports_dir):
        file_path = "{}/{}".format(reports_dir, application_file)
        f = open(file_path)
        data = json.load(f)

        evaluation_reports = data['evaluation_reports']
        application_info = data['application_info']

        # Get the policy violations for all evaluations reports (check first we have reports)
        if bool(evaluation_reports):
            for evaluation_report in evaluation_reports:
                stage = evaluation_report["stage"]
                application_id = evaluation_report["applicationId"]
                evaluation_date = evaluation_report["evaluationDate"]
                latest_report_url = evaluation_report["latestReportHtmlUrl"]
                report_url = evaluation_report["reportHtmlUrl"]
                report_pdf_url = evaluation_report["reportPdfUrl"]
                report_data_url = evaluation_report["reportDataUrl"]

                # https://help.sonatype.com/iqserver/automating/rest-apis/report-related-rest-apis---v2#ReportrelatedRESTAPIsv2-PolicyViolationsbyReportRESTAPI(v2)
                end_point = report_data_url.replace('/raw', '/policy')
                policy_violations = get_nexusiq_data(end_point)

                json_file = "{}/{}_{}.json".format(violations_dir, stage, application_info['name'])
                to_json_file(json_file, policy_violations)

    return



def get_remediation_info():
    #  https://help.sonatype.com/iqserver/automating/rest-apis/component-remediation-rest-api---v2

    # POST /api/v2/components/remediation/application/{applicationInternalId}?stageId={stageId}&identificationSource={identificationSource}&scanId={scanId}
    # end_point = "{}/{}?stageId={}&identificationSource={}&scanId={}".format(remediation_api, application_id, stage, identificationSource, scanId)

    remediation_api = 'api/v2/components/remediation/application'

    for report_violations_file in os.listdir(violations_dir):
        file_path = "{}/{}".format(violations_dir, report_violations_file)
        f = open(file_path)
        data = json.load(f)

        report_time = data["reportTime"]
        application_id = data['application']['id']
        application_public_id = data['application']['publicId']
        application_name = data['application']['name']
        organization_id = data['application']['organizationId']
        stage = report_violations_file[:report_violations_file.index('_')]

        application_remediation_endpoint = "{}/{}?stageId={}".format(remediation_api, application_id, stage)

        # Store remediation information is a directory per application
        application_dir = "{}/{}".format(remediations_dir, application_name)
        os.mkdir(application_dir)

        # Get the remediation information for each component in this report
        # NB. Each component is in this list because it has a policy violation
        components = data['components']

        for component in components:
            payload = {}
            payload['packageUrl'] = component['packageUrl']
            component_remediation = get_nexusiq_data_with_payload(application_remediation_endpoint, payload)

            component_dir = component['packageUrl']
            component_dir = component_dir.replace('/', '_')
            component_dir = component_dir.replace('?', '_')
            component_dir = component_dir.replace(':', '_')
            component_dir = component_dir.replace('=', '_')
            component_dir = component_dir.replace('@', '_')
            component_dir = component_dir.replace('%', '_')

            json_file = "{}/{}_{}.json".format(application_dir, stage, component_dir)
            to_json_file(json_file, component_remediation)

    return



def main():
    init()

    # Get a list of all applications
    all_applications = get_all_applications()

    # Get evaluation report details for all applications
    get_evaluation_reports(all_applications)

    # Get the policy violations in all evaluation reports
    get_policy_violations()

    # Get remediation information for violations in each report
    get_remediation_info()


if __name__ == '__main__':
    main()