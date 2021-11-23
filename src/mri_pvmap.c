#include "mrilib.h"

#include "despike_inc.c"

/*-----------------------------------------------------------------*/

static float r2D( int n , float *a , float *b , float *x )
{
   float sax=0.0f , sbx=0.0f , sxx=0.0f ; int ii ;

   for( ii=0 ; ii < n ; ii++ ){
     sax += x[ii]*a[ii] ;
     sbx += x[ii]*b[ii] ;
     sxx += x[ii]*x[ii] ;
   }
   if( sxx <= 0.0001f ) return 0.0f ;
   sax = (sax*sax+sbx*sbx)/sxx ;
#if 0
   if( sax > 1.0f ) sax = 1.0f ;
#endif
   return sax ;
}

/*----------------------------------------------------------------*/

static int    nvec=0 ;
static float *uvec=NULL , *vvec=NULL ;
static float  ulam=0.0f ,  vlam=0.0f ;

MRI_IMAGE * mri_pvmap_get_vecpair(void)
{
  MRI_IMAGE *uvim ;

  if( nvec == 0 || uvec == NULL || vvec == NULL ) return NULL ;

  uvim = mri_new( nvec , 2 , MRI_float ) ;
  memcpy( MRI_FLOAT_PTR(uvim)      , uvec , sizeof(float)*nvec ) ;
  memcpy( MRI_FLOAT_PTR(uvim)+nvec , vvec , sizeof(float)*nvec ) ;
  return uvim ;
}

float_pair mri_pvmap_get_lampair(void)
{
   float_pair uvlam ;
   uvlam.a = ulam ; uvlam.b = vlam ; return uvlam ;
}

/*----------------------------------------------------------------*/

MRI_IMAGE * mri_vec_to_pvmap( MRI_IMAGE *inim )
{
   Aint nx , ny , ii ;
   float_pair svals ;
   MRI_IMAGE *outim ;
   float     *outar , *iar ;
   unsigned short xran[3] ;
   static int ncall=0 ;

ENTRY("mri_vec_to_pvmap") ;

   if( inim == NULL || inim->kind != MRI_float ) RETURN(NULL) ;

   nx = inim->nx ; if( nx < 9 ) RETURN(NULL) ;
   ny = inim->ny ; if( ny < 9 ) RETURN(NULL) ;

   if( nx != nvec || uvec == NULL || vvec == NULL ){
     uvec = (float *)realloc(uvec,sizeof(float)*nx) ;
     vvec = (float *)realloc(vvec,sizeof(float)*nx) ;
   }
   nvec = nx ;

   xran[0] = (unsigned short)(nx+ny+73) ;
   xran[1] = (unsigned short)(nx-ny+473+ncall) ; ncall++ ;
   xran[2] = (unsigned short)(nx*ny+7) ;

   iar   = MRI_FLOAT_PTR(inim) ;
   svals = principal_vector_pair( nx , ny , 0 , iar ,
                                  uvec , vvec , NULL , NULL , xran ) ;

#if 0
INFO_message("mri_vec_to_pvmap: svals = %g %g",svals.a,svals.b) ;
for( ii=0 ; ii < nx ; ii++ ){
  printf(" %g %g\n",uvec[ii],vvec[ii]) ;
}
#endif

   ulam = svals.a ; vlam = svals.b ;

   if( svals.a < 0.0f || svals.b < 0.0f ) RETURN(NULL) ;

   outim = mri_new( ny , 1 , MRI_float ) ;
   outar = MRI_FLOAT_PTR(outim) ;

   THD_normalize(nx,uvec) ;
   THD_normalize(nx,vvec) ;

#if 0
INFO_message("uvec %g   svec %g",svals.a,svals.b) ;
for( ii=0 ; ii < nx ; ii++ )
  fprintf(stderr," %7.4f %7.4f\n",uvec[ii],vvec[ii]) ;
#endif

   for( ii=0 ; ii < ny ; ii++ ){
     outar[ii] = r2D( nx , uvec , vvec , iar+ii*nx ) ;
   }

   RETURN(outim) ;
}

/*-----------------------------------------------------------------*/

MRI_IMAGE * THD_dataset_to_pvmap( THD_3dim_dataset *dset , byte *mask )
{
   int nvox, npt, nmask, ii,jj , polort ;
   MRI_IMAGE *inim, *tim, *outim ;
   float *inar, *tar, *outar, *dar ;

ENTRY("THD_dataset_to_pvmap") ;

   if( !ISVALID_DSET(dset) ) RETURN(NULL) ;

   nvox = DSET_NVOX(dset) ;
   npt  = DSET_NVALS(dset) ;
   if( nvox < 9 || npt < 9 ) RETURN(NULL) ;

   if( mask != NULL ){
     nmask = THD_countmask( nvox , mask ) ;
     if( nmask < 9 ) RETURN(NULL) ;
   } else {
     nmask = nvox ;
   }

   inim = mri_new( npt , nmask , MRI_float ) ;
   inar = MRI_FLOAT_PTR(inim) ;
   dar  = (float *)malloc(sizeof(float)*npt) ;
   tar  = (float *)malloc(sizeof(float)*npt*3) ;

   DSET_load(dset) ;

   polort = npt / 50 ;                   /* 24 Apr 2019 */
        if( polort <  2 ) polort = 2 ;   /* change detrending */
   else if( polort > 20 ) polort = 20 ;

   for( jj=ii=0 ; ii < nvox ; ii++ ){
     if( mask == NULL || mask[ii] != 0 ){
       THD_extract_array( ii , dset , 0 , dar ) ;
       DES_despike25( npt , dar , tar ) ;    /* despiking */
#if 0
       THD_cubic_detrend( npt , dar ) ;      /* detrending */
#else
       THD_generic_detrend_LSQ( npt , dar , polort , 0,NULL,NULL ) ;
#endif
       THD_normalize( npt , dar ) ;          /* L2 normalize */
       memcpy( inar+jj*npt , dar , sizeof(float)*npt ) ;
       jj++ ;
     }
   }

   free(tar) ; free(dar) ;

   tim = mri_vec_to_pvmap( inim ) ;

   mri_free(inim) ;

   if( nmask == nvox ) RETURN(tim) ;

   outim = mri_new( nvox , 1 , MRI_float ) ;
   outar = MRI_FLOAT_PTR(outim) ;
   tar   = MRI_FLOAT_PTR(tim) ;

   for( jj=ii=0 ; ii < nvox ; ii++ ){
     if( mask == NULL || mask[ii] != 0 ) outar[ii] = tar[jj++] ;
     else                                outar[ii] = 0.0f ;
   }

   mri_free(tim) ;

   RETURN(outim) ;
}
