module wave3d_solver
   implicit none
contains

   subroutine simulate_wave_3d(dt, dx, nx, ny, nz, n_steps, u_out)
      implicit none
      real(8), intent(in) :: dt, dx
      integer, intent(in) :: nx, ny, nz, n_steps
      real(8), intent(out) :: u_out(nx, ny, nz)

      if (n_steps < 0) then
         stop 2
      end if
      if (nx <= 0 .or. ny <= 0 .or. nz <= 0) then
         stop 2
      end if
      if (dx <= 0.0d0 .or. dt < 0.0d0) then
         stop 2
      end if

      u_out = 0.0d0
   end subroutine simulate_wave_3d

end module wave3d_solver
