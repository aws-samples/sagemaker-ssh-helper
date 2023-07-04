import sagemaker
from sagemaker import Session
# noinspection PyProtectedMember
from sagemaker.estimator import _TrainingJob

# This a fictitious IAM role ARN to construct detached SageMaker jobs
FICTITIOUS_IAM_ROLE = 'arn:aws:iam::444455556666:role/Admin'


class DetachedEstimator(sagemaker.estimator.EstimatorBase):
    f"""
    A sagemaker.estimator.Estimator that does not block on attach().
    """

    def __init__(self, training_job_name: str, sagemaker_session: Session):
        super().__init__(sagemaker_session=sagemaker_session,
                         instance_count=0, instance_type='ml.m5.xlarge',
                         role=FICTITIOUS_IAM_ROLE)
        self._current_job_name = training_job_name
        self.latest_training_job = _TrainingJob(sagemaker_session, self._current_job_name)

    def training_image_uri(self):
        raise ValueError("Not implemented")

    def hyperparameters(self):
        raise ValueError("Not implemented")

    def create_model(self, **kwargs):
        raise ValueError("Not implemented")

    @classmethod
    def attach(cls, training_job_name: str, sagemaker_session: Session = None,
               model_channel_name="model"):
        if not isinstance(training_job_name, str):
            raise ValueError("training_job_name MUST be a string")
        # TODO: fetch job details and call _prepare_init_params_from_job_description()
        return DetachedEstimator(training_job_name, sagemaker_session)


class DetachedProcessor(sagemaker.processing.Processor):
    f"""
    A sagemaker.processing.Processor that has attach().
    """

    def __init__(self, processing_job_name: str, sagemaker_session: Session):
        super().__init__(sagemaker_session=sagemaker_session, instance_count=0, role=FICTITIOUS_IAM_ROLE)
        self._current_job_name = processing_job_name
        self.latest_job = sagemaker.processing.ProcessingJob(sagemaker_session, self._current_job_name, [], [])

    @classmethod
    def attach(cls, processing_job_name: str, sagemaker_session: Session = None):
        if not isinstance(processing_job_name, str):
            raise ValueError("processing_job_name MUST be a string")
        return DetachedProcessor(processing_job_name, sagemaker_session)
