module wave3d_solver
   implicit none
contains

   subroutine apply_periodic_ghosts(a, nx, ny, nz)
      implicit none
      integer, intent(in) :: nx, ny, nz
      real(8), intent(inout) :: a(:, :, :)

   end subroutine apply_periodic_ghosts

   subroutine push_wave_3d(u, v, dt, dx, nx, ny, nz)
      implicit none
      real(8), intent(inout) :: u(:, :, :), v(:, :, :)
      real(8), intent(in) :: dt, dx
      integer, intent(in) :: nx, ny, nz

   end subroutine push_wave_3d

end module wave3d_solver
