# -*- coding: utf-8 -*- #
# Copyright 2023 Google LLC. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Migrate data from a source database to Cloud Spanner given a schema."""
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import textwrap

from googlecloudsdk.calliope import base
from googlecloudsdk.command_lib.spanner import flags
from googlecloudsdk.command_lib.spanner import migration_backend


@base.DefaultUniverseOnly
class Data(base.BinaryBackedCommand):
  """Migrate data from a source database to Cloud Spanner given a schema."""

  detailed_help = {
      'EXAMPLES':
          textwrap.dedent("""\
        To copy data to Cloud Spanner given a session file:

          $ {command} --session=./session.json --source=postgresql < ~/cart.pg_dump --target-profile='instance=spanner-instance'
      """),
  }

  @staticmethod
  def Args(parser):
    """Register the flags for this command."""
    flags.GetSpannerMigrationSourceFlag().AddToParser(parser)
    flags.GetSpannerMigrationSessionFlag().AddToParser(parser)
    flags.GetSpannerMigrationPrefixFlag().AddToParser(parser)
    flags.GetSpannerMigrationSkipForeignKeysFlag().AddToParser(parser)
    flags.GetSpannerMigrationSourceProfileFlag().AddToParser(parser)
    flags.GetSpannerMigrationTargetFlag().AddToParser(parser)
    flags.GetSpannerMigrationTargetProfileFlag().AddToParser(parser)
    flags.GetSpannerMigrationWriteLimitFlag().AddToParser(parser)
    flags.GetSpannerMigrationDryRunFlag().AddToParser(parser)
    flags.GetSpannerMigrationLogLevelFlag().AddToParser(parser)
    flags.GetSpannerMigrationProjectFlag().AddToParser(parser)
    flags.GetSpannerMigrationDataflowTemplateFlag().AddToParser(parser)

  def Run(self, args):
    """Run the data command."""
    command_executor = migration_backend.SpannerMigrationWrapper()
    env_vars = migration_backend.GetEnvArgsForCommand(
        extra_vars={'GCLOUD_HB_PLUGIN': 'true'})
    response = command_executor(
        command='data',
        source=args.source,
        session=args.session,
        prefix=args.prefix,
        skip_foreign_keys=args.skip_foreign_keys,
        source_profile=args.source_profile,
        target=args.target,
        target_profile=args.target_profile,
        write_limit=args.write_limit,
        dry_run=args.dry_run,
        log_level=args.log_level,
        project=args.project,
        dataflow_template=args.dataflow_template,
        env=env_vars,
    )
    self.exit_code = response.exit_code
    return self._DefaultOperationResponseHandler(response)
