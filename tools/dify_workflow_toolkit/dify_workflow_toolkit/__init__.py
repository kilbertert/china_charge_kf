"""Reusable Dify workflow deployment toolkit.

Build, validate, deploy and verify Dify workflow DSL files end-to-end:

    from dify_workflow_toolkit import Workflow, StartNode, LLMNode, CodeNode, EndNode

    wf = Workflow(name="my_app", description="...")
    wf.add(StartNode(variables=[...]))
    wf.add(LLMNode(id="4080", title="classifier",
                   system_prompt="...", user_prompt="..."))
    wf.add(CodeNode(id="4002", title="safety_net",
                    code="def main(...): ..."))
    wf.add(EndNode(outputs=[...]))
    wf.connect("4001", "4080")
    wf.connect("4080", "4002")
    wf.connect("4002", "4099")

    yml_text = wf.to_yaml()

    from dify_workflow_toolkit import Deployer
    deployer = Deployer(ssh_host="...", ssh_user="root", ssh_password="...")
    deployer.deploy(yml_text, app_id="...", restart=True)
"""

from dify_workflow_toolkit.builder import (
    CodeNode,
    Edge,
    EndNode,
    IfElseNode,
    KnowledgeRetrievalNode,
    LLMNode,
    Node,
    StartNode,
    Variable,
    VariableAggregatorNode,
    Workflow,
)
from dify_workflow_toolkit.deployer import Deployer, DeploymentResult
from dify_workflow_toolkit.ssh_client import SSHClient
from dify_workflow_toolkit.verifier import TestCase, Verifier, run_test_cases
from dify_workflow_toolkit.yml_validator import ValidationError, validate_yaml

__version__ = "0.1.0"

__all__ = [
    "CodeNode",
    "Deployer",
    "DeploymentResult",
    "Edge",
    "EndNode",
    "IfElseNode",
    "KnowledgeRetrievalNode",
    "LLMNode",
    "Node",
    "SSHClient",
    "StartNode",
    "TestCase",
    "Variable",
    "VariableAggregatorNode",
    "Verifier",
    "Workflow",
    "run_test_cases",
    "validate_yaml",
    "ValidationError",
]
