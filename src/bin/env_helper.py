from typing import Dict

from projen.awscdk import AwsCdkPythonApp


def cdk_action_task(project: AwsCdkPythonApp, target_account: Dict[str, str]):
    task_actions = ["synth", "diff", "deploy", "destroy"]
    stack_name_pattern = f"*Stack-{target_account['ENVIRONMENT']}"

    for action in task_actions:
        task_name = f"{target_account['ENVIRONMENT']}:{action}"
        task_description = f"{action.capitalize()} the stacks on the {target_account['ENVIRONMENT'].upper()} account"

        exec_command = f"cdk {action} --require-approval never {stack_name_pattern}"
        if action == "destroy":
            exec_command = f"cdk destroy --force {stack_name_pattern}"
        if action == "synth":
            exec_command = "cdk synth"

        project.add_task(
            task_name,
            description=task_description,
            env=target_account,
            exec=exec_command,
        )
