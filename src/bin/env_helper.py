from projen.awscdk import AwsCdkPythonApp

CDK_VALIDATE_COMMAND = "cdk --unstable=validate validate"


def cdk_action_task(project: AwsCdkPythonApp, target_account: dict[str, str]):
    stack_name_pattern = f"*Stack-{target_account['ENVIRONMENT']}"
    action_commands = {
        "synth": "cdk synth",
        "validate": CDK_VALIDATE_COMMAND,
        "diff": f"cdk diff --require-approval never {stack_name_pattern}",
        "deploy": f"cdk deploy --require-approval never {stack_name_pattern}",
        "destroy": f"cdk destroy --force {stack_name_pattern}",
    }

    for action, exec_command in action_commands.items():
        task_name = f"{target_account['ENVIRONMENT']}:{action}"
        task_description = f"{action.capitalize()} the stacks on the {target_account['ENVIRONMENT'].upper()} account"

        task = project.add_task(
            task_name,
            description=task_description,
            env=target_account,
        )
        task.exec(exec_command, receive_args=True if action == "validate" else None)
