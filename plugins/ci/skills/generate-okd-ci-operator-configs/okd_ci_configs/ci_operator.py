"""Build and write ci-operator YAML configurations for images and repositories."""

from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from .helpers import ImageCoordinate, deep_get
from .metadata import ImageMetaInfo, get_okd_payload_tag_name


class CiOperatorImageConfig:

    def __init__(
        self,
        meta: ImageMetaInfo,
        promotion_namespace: str,
        promotion_imagestream: str,
    ):
        self.meta = meta
        self.promotion_namespace = promotion_namespace
        self.promotion_imagestream = promotion_imagestream
        self.dockerfile_path: str = 'Dockerfile'
        self.context_dir: Optional[str] = None
        self.payload_tag = get_okd_payload_tag_name(meta)
        self.base_image: Optional[ImageCoordinate] = None
        self.coordinate = ImageCoordinate(
            namespace=promotion_namespace,
            name=promotion_imagestream,
            tag=self.payload_tag,
        )
        self.replacements: Dict[ImageCoordinate, List[str]] = {}

    def add_replacement(self, coord: ImageCoordinate, replace_list: List[str]):
        self.replacements[coord] = replace_list

    def add_from(self, coord: ImageCoordinate):
        self.base_image = coord

    def set_dockerfile_path(self, path: str):
        self.dockerfile_path = path.lstrip('/')

    def set_context_dir(self, context_dir: str):
        self.context_dir = context_dir

    def get_obj(
        self,
        ci_operator_image_names: Dict[ImageCoordinate, str],
    ) -> Tuple[Dict, Dict]:
        """
        Produce the image entry dict and optional raw_step dict.
        Matches ``CiOperatorImageConfig.get_obj`` in the original.
        """
        meta = self.meta
        base_obj: dict = {}
        raw_step: dict = {}

        build_args: List[dict] = [{'name': 'TAGS', 'value': 'scos'}]
        extra_args = deep_get(meta.okd_alignment, 'build_args')
        if extra_args and isinstance(extra_args, list):
            build_args.extend(extra_args)

        inject_repos = deep_get(meta.okd_alignment, 'inject_rpm_repositories')
        if inject_repos:
            intermediate_tag = f'pre-repo-{self.payload_tag}'
            repo_def_lines: List[str] = []
            for entry in inject_repos:
                repo_id = entry.get('id', '')
                baseurl = entry.get('baseurl', '')
                if not repo_id or not baseurl:
                    raise ValueError(
                        f'Incomplete repo injection data for {meta.distgit_key}: '
                        f'{repo_id} / {baseurl}'
                    )
                repo_def_lines.extend([
                    f'[{repo_id}]',
                    f'id = {repo_id}',
                    f'name = {repo_id}',
                    f'baseurl = {baseurl}',
                    'enabled = 1',
                    'gpgcheck = 0',
                    'sslverify = false',
                    'skip_if_unavailable = true',
                    '',
                ])
            repo_lines = '\n'.join(repo_def_lines)
            raw_step = {
                'pipeline_image_cache_step': {
                    'commands': f"""
cat << EOF > /etc/yum.repos.d/art.repo
{repo_lines}
EOF
        """,
                    'from': ci_operator_image_names[self.base_image],
                    'to': intermediate_tag,
                },
            }
            base_obj = {
                'build_args': build_args,
                'from': intermediate_tag,
                'to': self.payload_tag,
            }
        else:
            base_obj = {
                'build_args': build_args,
                'to': self.payload_tag,
            }
            if self.base_image:
                base_obj['from'] = ci_operator_image_names[self.base_image]

        prowjob_dockerfile_path = self.dockerfile_path
        if self.context_dir:
            base_obj['context_dir'] = self.context_dir
            if prowjob_dockerfile_path.startswith(self.context_dir):
                prowjob_dockerfile_path = prowjob_dockerfile_path[len(self.context_dir):].lstrip('/')
            else:
                raise ValueError('Expected dockerfile path to start with context_dir')

        if self.dockerfile_path:
            base_obj['dockerfile_path'] = prowjob_dockerfile_path

        inputs: dict = {}
        for coord, replacements in self.replacements.items():
            inputs[ci_operator_image_names[coord]] = {'as': replacements}
        if inputs:
            base_obj['inputs'] = inputs

        return base_obj, raw_step


# ---------------------------------------------------------------------------
# ci-operator config (per-repo)
# ---------------------------------------------------------------------------

class CiOperatorConfig:

    def __init__(
        self,
        org: str,
        repo: str,
        branch: str,
        promotion_namespace: str,
        promotion_imagestream: str,
    ):
        self.org = org
        self.repo = repo
        self.branch = branch
        self.promotion_namespace = promotion_namespace
        self.promotion_imagestream = promotion_imagestream
        self.image_configs: OrderedDict[str, CiOperatorImageConfig] = OrderedDict()
        self.promotion = {
            'to': [
                {
                    'namespace': promotion_namespace,
                    'name': promotion_imagestream,
                },
            ],
        }
        self.build_root: Optional[dict] = None
        self.releases: dict = {}
        self.complete = False

    def get_image_config(self, meta: ImageMetaInfo) -> CiOperatorImageConfig:
        if meta.distgit_key not in self.image_configs:
            self.image_configs[meta.distgit_key] = CiOperatorImageConfig(
                meta, self.promotion_namespace, self.promotion_imagestream,
            )
        return self.image_configs[meta.distgit_key]

    def add_release(self, name: str, release_def: Dict):
        self.releases[name] = release_def

    def set_build_root(self, coord: ImageCoordinate):
        self.build_root = coord.as_dict()

    def get_config_path(self, output_dir: Path) -> Path:
        return (
            output_dir
            / self.org
            / self.repo
            / f'{self.org}-{self.repo}-{self.branch}__okd-scos.yaml'
        )

    def write_config(self, output_dir: Path, dry_run: bool = False) -> Optional[Path]:
        output_path = self.get_config_path(output_dir)

        if not self.complete:
            print(f'  Refusing to write: {output_path} (reconciliation did not complete)')
            return None

        # Build the name mapping.
        # Start by assuming all dependencies are base images.
        ci_names: Dict[ImageCoordinate, str] = {}
        base_image_defs: OrderedDict[ImageCoordinate, bool] = OrderedDict()

        for _, img_cfg in self.image_configs.items():
            for coord in img_cfg.replacements:
                base_image_defs[coord] = True
                ci_names[coord] = coord.unique_key()
            if img_cfg.base_image:
                base_image_defs[img_cfg.base_image] = True
                ci_names[img_cfg.base_image] = img_cfg.base_image.unique_key()

        # Remove images we build ourselves from base_image_defs.
        for _, img_cfg in self.image_configs.items():
            if img_cfg.coordinate in base_image_defs:
                base_image_defs.pop(img_cfg.coordinate)
            ci_names[img_cfg.coordinate] = img_cfg.payload_tag

        images: List[dict] = []
        raw_steps: List[dict] = []
        for _, img_cfg in self.image_configs.items():
            image_obj, raw_step = img_cfg.get_obj(ci_names)
            images.append(image_obj)
            if raw_step:
                raw_steps.append(raw_step)

        base_images: Dict[str, dict] = {}
        for coord in base_image_defs:
            base_images[ci_names[coord]] = coord.as_dict()

        config: dict = {
            'images': images,
            'promotion': self.promotion,
            'resources': {
                '*': {
                    'requests': {
                        'cpu': '100m',
                        'memory': '200Mi',
                    },
                },
            },
        }
        if raw_steps:
            config['raw_steps'] = raw_steps
        if base_images:
            config['base_images'] = base_images
        if self.build_root:
            config['build_root'] = {'image_stream_tag': self.build_root}
        if self.releases:
            config['releases'] = self.releases

        if dry_run:
            print(f'\n--- DRY RUN: {output_path} ---')
            print(yaml.safe_dump(config, default_flow_style=False))
            return output_path

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(yaml.safe_dump(config, default_flow_style=False))
        print(f'  Wrote: {output_path}')
        return output_path


# ---------------------------------------------------------------------------
# ci-operator configs collection (all repos)
# ---------------------------------------------------------------------------

class CiOperatorConfigs:

    def __init__(self, promotion_namespace: str, promotion_imagestream: str):
        self.configs: Dict[str, CiOperatorConfig] = {}
        self.promotion_namespace = promotion_namespace
        self.promotion_imagestream = promotion_imagestream

    def get_config(self, org: str, repo: str, branch: str) -> CiOperatorConfig:
        key = f'{org}:{repo}:{branch}'
        if key not in self.configs:
            self.configs[key] = CiOperatorConfig(
                org, repo, branch,
                self.promotion_namespace, self.promotion_imagestream,
            )
        return self.configs[key]

    def write_configs(self, output_dir: Path, dry_run: bool = False) -> List[Path]:
        written: List[Path] = []
        for _, config in self.configs.items():
            path = config.write_config(output_dir, dry_run)
            if path:
                written.append(path)
        return written
