#!/usr/bin/env python3

import aws_cdk as cdk

from plantdex_stack import PlantDexStack

app = cdk.App()

PlantDexStack(
    app,
    "PlantDexStack",
)

app.synth()