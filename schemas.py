from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
import datetime

class OrchestratorInput(BaseModel):
    """Input schema for the orchestrator agent"""
    role: str = Field(..., description="The job role/position")
    industry: str = Field(..., description="The industry sector")
    question: str = Field(..., description="The interview question")
    resume: str = Field(default="", description="Optional resume text")
    jobDescription: str = Field(default="", description="Optional job description")

class STARResponse(BaseModel):
    """STAR format interview responses"""
    situation: str = Field(default="Not provided", description="The description of the situation, context, or background of the experience.")
    task: str = Field(default="Not provided", description="The explanation of the specific task, responsibility, objective, or challenge faced.")
    action: str = Field(default="Not provided", description="The detailed description of the specific actions taken by the individual to address the situation or task.")
    result: str = Field(default="Not provided", description="The description of the outcomes, achievements, accomplishments, or lessons learned as a result of the actions.")

class Critique(BaseModel):
    """STAR answer critiques"""
    rating: float = Field(..., ge=0.0, le=5.0, description="Overall numerical rating of the STAR answer (1.0-5.0).")
    structureFeedback: Optional[str] = Field(default=None, description="Specific feedback on the answer's adherence to the STAR structure.")
    relevanceFeedback: Optional[str] = Field(default=None, description="Specific feedback on how relevant the answer is to the role, industry, and question asked.")
    specificityFeedback: Optional[str] = Field(default=None, description="Specific feedback on the use of concrete details, examples, metrics, and quantifiable results.")
    professionalImpactFeedback: Optional[str] = Field(default=None, description="Specific feedback on the professionalism, tone, and demonstrated impact of the answer.")
    suggestions: List[str] = Field(default_factory=list, description="A list of 2-3 concrete, actionable suggestions for improving the STAR answer.")
    rawCritiqueText: Optional[str] = Field(default=None, description="Internal field for full critique text.")
    feedback: Optional[str] = Field(default=None, description="Overall feedback summary.")

class IterationData(BaseModel):
    """Data for a single iteration of the STAR answer generation process"""
    iterationNumber: int = Field(..., description="The iteration number, starting from 1")
    starAnswer: STARResponse = Field(..., description="The STAR format answer for this iteration")
    critique: Critique = Field(..., description="The critique feedback for this iteration")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(), description="The timestamp when this iteration was created (UTC)")

class PerformanceMetrics(BaseModel):
    """Timing metrics for the STAR answer generation process"""
    totalWorkflowTime: float = Field(..., description="Total time taken for the entire workflow")
    generationTime: float = Field(..., description="Time taken for initial generation")
    critiqueTimes: List[float] = Field(default_factory=list, description="Times taken for each critique iteration")
    refinementTimes: List[float] = Field(default_factory=list, description="Times taken for each refinement iteration")

class ResponseMetadata(BaseModel):
    """Metadata for the STAR answer generation response"""
    role: str = Field(..., description="The job role/position")
    industry: str = Field(..., description="The industry sector")
    question: str = Field(..., description="The interview question")
    resume: str = Field(default="", description="Optional resume information")
    jobDescription: str = Field(default="", description="Optional job description")
    status: str = Field(default="COMPLETED", description="The status of the answer generation process")
    createdAt: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(), description="The timestamp when this response was created (UTC)")
    userId: str = Field(default="", description="The ID of the user who generated this response")

class FinalResponse(BaseModel):
    """Complete response from the STAR answer generation process"""
    metadata: ResponseMetadata = Field(..., description="Metadata about the response")
    iterations: List[IterationData] = Field(default_factory=list, description="All iterations of the answer generation process")
    performanceMetrics: PerformanceMetrics = Field(..., description="Performance metrics for the process")

    def get_best_star_answer(self) -> STARResponse:
        """Utility method to get the highest rated STAR answer from iterations"""
        if not self.iterations:
            return STARResponse()

        # Find the highest rated iteration
        highest_rated = max(self.iterations, key=lambda x: x.critique.rating)
        return highest_rated.starAnswer