from projen.awscdk import AwsCdkPythonApp


def cdk_action_task(project: AwsCdkPythonApp, target_account: dict[str, str]):
    stack_name_pattern = f"*Stack-{target_account['ENVIRONMENT']}"
    action_commands = {
        "synth": ("cdk synth", False),
        "validate": ("cdk --unstable=validate validate", True),
        "diff": (f"cdk diff --require-approval never {stack_name_pattern}", False),
        "deploy": (f"cdk deploy --require-approval never {stack_name_pattern}", False),
        "destroy": (f"cdk destroy --force {stack_name_pattern}", False),
    }

    for action, (exec_command, receive_args) in action_commands.items():
        task_name = f"{target_account['ENVIRONMENT']}:{action}"
        task_description = f"{action.capitalize()} the stacks on the {target_account['ENVIRONMENT'].upper()} account"

        task = project.add_task(
            task_name,
            description=task_description,
            env=target_account,
        )
        if receive_args:
            task.exec(exec_command, receive_args=True)
        else:
            task.exec(exec_command)
