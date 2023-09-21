library identifier: 'waldo', changelog: false

pipeline {
    agent any
    options {
        skipDefaultCheckout true
    }
    parameters {
        string(name: 'email', defaultValue: 'de.pdk.automation@intel.com', description: 'Whitespace separator for multiple emails')
        string(name: 'root_dir', defaultValue: '/nfs/site/disks/pdk_jenkins_01/qa', description: '')
        string(name: 'wash_groups', defaultValue: 'users adg ciaf soc p1278', description: '')
        string(name: 'git_url', defaultValue: 'ssh://git@gitlab.devtools.intel.com:29418/pdk-qa/multi-branch/extraction.git', description: '')
        // string(name: 'pdktest_git_url', defaultValue: 'ssh://git@gitlab.devtools.intel.com:29418/pdk-qa/pdktest.git', description: '')
        string(name: 'cmd_opt', defaultValue: 'src --pconf extraction.conf --run-dir ./run --html ./run/results.html --junitxml=test_reports/results.xml', description: '')
    }
    environment {
        DKAT_SHARED = "/nfs/pdx/disks/de_pdk_automation_disk001/shared"
        HTTP_PROXY = "http://proxy-dmz.intel.com:911"
        HTTPS_PROXY = "http://proxy-dmz.intel.com:912"
        QA_WORK_DIR = "${params.root_dir}/${JOB_NAME}/${BUILD_NUMBER}"
        INTG_REPO = "extraction"
    }
    stages {
        stage('Tox') {
            steps {
                dir("${QA_WORK_DIR}") {
                    cloneRepo(
                        [
                            gitUrl: "${params.git_url}",
                            gitBranch: "${env.BRANCH_NAME}"
                        ]
                    )
                    // cloneRepo([gitUrl: "${params.pdktest_git_url}"])
                    sh """
                        cd "${QA_WORK_DIR}/${INTG_REPO}"
                        ${DKAT_SHARED}/bin/tox -- src --co
                    """
                }
            }
        }
        stage('QA') {
            steps {
                runTest(
                    [
                        stageName: 'pdktest',
                        rootDir: "${QA_WORK_DIR}",
                        gitUrl: "${params.git_url}",
                        washGrp: "${params.wash_groups}",
                        cmdOpt: "${params.cmd_opt}",
                    ]
                )
            }
        }
    }
    post {
        always {
            publishResults("${QA_WORK_DIR}")
            uploadArtifacts("${QA_WORK_DIR}", ["${INTG_REPO}/results.*"])
        }
        changed {
            sendEmail("${params.email}")
        }
    }
}
