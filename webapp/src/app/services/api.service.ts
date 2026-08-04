import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  AvailableCountiesResponse,
  AvailableStatesResponse,
  BuildingEnergyModelRequest,
  BuildingEnergyModelResponse,
  BuildingTypesResponse,
  CompositeResolveRequest,
  CompositeResolveResponse,
  EnergyStarTypeInfo,
  EuiDistributionRequest,
  EuiDistributionResponse,
  EuiPercentileBuildingsRequest,
  EuiPercentileBuildingsResponse,
  MeasuresCompareRequest,
  MeasuresCompareResponse,
  MeasuresListResponse,
  MetadataSummaryRequest,
  MetadataSummaryResponse,
  MosExportRequest,
  Product,
  TimeseriesRequest,
  TimeseriesResponse,
} from '../models/api.models';

/** Thin HttpClient wrapper for the composite building explorer API (see api/main.py). */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly baseUrl = environment.apiBaseUrl;

  constructor(private readonly http: HttpClient) {}

  getEnergyStarTypes(): Observable<EnergyStarTypeInfo[]> {
    return this.http.get<EnergyStarTypeInfo[]>(`${this.baseUrl}/energy-star-types`);
  }

  getBuildingTypes(product: Product): Observable<BuildingTypesResponse> {
    const params = new HttpParams().set('product', product);
    return this.http.get<BuildingTypesResponse>(`${this.baseUrl}/building-types`, { params });
  }

  resolveComposite(request: CompositeResolveRequest): Observable<CompositeResolveResponse> {
    return this.http.post<CompositeResolveResponse>(`${this.baseUrl}/composite/resolve`, request);
  }

  getMetadataSummary(request: MetadataSummaryRequest): Observable<MetadataSummaryResponse> {
    return this.http.post<MetadataSummaryResponse>(`${this.baseUrl}/metadata/summary`, request);
  }

  getEuiDistribution(request: EuiDistributionRequest): Observable<EuiDistributionResponse> {
    return this.http.post<EuiDistributionResponse>(`${this.baseUrl}/composite/eui-distribution`, request);
  }

  getEuiPercentileBuildings(request: EuiPercentileBuildingsRequest): Observable<EuiPercentileBuildingsResponse> {
    return this.http.post<EuiPercentileBuildingsResponse>(`${this.baseUrl}/composite/eui-percentile-buildings`, request);
  }

  getCompositeTimeseries(request: TimeseriesRequest): Observable<TimeseriesResponse> {
    return this.http.post<TimeseriesResponse>(`${this.baseUrl}/timeseries/composite`, request);
  }

  getMeasures(product: Product, release?: string): Observable<MeasuresListResponse> {
    let params = new HttpParams().set('product', product);
    if (release) {
      params = params.set('release', release);
    }
    return this.http.get<MeasuresListResponse>(`${this.baseUrl}/measures`, { params });
  }

  getAvailableStates(product: Product, release?: string): Observable<AvailableStatesResponse> {
    let params = new HttpParams().set('product', product);
    if (release) {
      params = params.set('release', release);
    }
    return this.http.get<AvailableStatesResponse>(`${this.baseUrl}/locations/states`, { params });
  }

  getAvailableCounties(product: Product, state: string, release?: string): Observable<AvailableCountiesResponse> {
    let params = new HttpParams().set('product', product).set('state', state);
    if (release) {
      params = params.set('release', release);
    }
    return this.http.get<AvailableCountiesResponse>(`${this.baseUrl}/locations/counties`, { params });
  }

  compareMeasures(request: MeasuresCompareRequest): Observable<MeasuresCompareResponse> {
    return this.http.post<MeasuresCompareResponse>(`${this.baseUrl}/measures/compare`, request);
  }

  exportMos(request: MosExportRequest): Observable<Blob> {
    return this.http.post(`${this.baseUrl}/export/mos`, request, { responseType: 'blob' });
  }

  getBuildingEnergyModelManifest(request: BuildingEnergyModelRequest): Observable<BuildingEnergyModelResponse> {
    return this.http.post<BuildingEnergyModelResponse>(`${this.baseUrl}/composite/building-models/manifest`, request);
  }

  downloadBuildingEnergyModels(request: BuildingEnergyModelRequest): Observable<Blob> {
    return this.http.post(`${this.baseUrl}/composite/building-models`, request, { responseType: 'blob' });
  }
}
